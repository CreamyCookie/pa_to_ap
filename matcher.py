# Copyright 2021 Joschua Gandert
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.

from difflib import SequenceMatcher
from operator import itemgetter
from typing import Generic, TypeVar, Mapping, Callable, Any, Union, List, \
    Sequence, Optional, Tuple


T = TypeVar('T')
Real = Union[int, float]
AttributeGetter = Callable[[T], Any]
AttributeGetterToWeight = Mapping[AttributeGetter, Real]

SUPPORTED_NUMBER_TYPES = (int, float)


class _MatchData:
    def __init__(self, a_idx, a_value, b_size):
        self.a_idx = a_idx
        self.a_value = a_value
        self.b_idx_to_similarity = [0 for _ in range(b_size)]

        self.best_b_idx = -1
        self.best_b_similarity = float('-inf')
        self.second_best_b_idx = -1
        self.second_best_b_similarity = float('-inf')
        self.found_best = False

        self.continue_attr_index = 0

        # rarely needed since in a lot of cases there won't be conflicts
        self._sorted_b_similarity_with_idx_pairs = None
        self.is_fully_measured = False

    def add_similarity(self, b_idx, similarity_part):
        self.b_idx_to_similarity[b_idx] += similarity_part
        b_idx_total_similarity = self.b_idx_to_similarity[b_idx]

        if b_idx_total_similarity > self.best_b_similarity:
            self.second_best_b_idx = self.best_b_idx
            self.second_best_b_similarity = self.best_b_similarity

            self.best_b_idx = b_idx
            self.best_b_similarity = b_idx_total_similarity
        elif b_idx_total_similarity > self.second_best_b_similarity:
            self.second_best_b_idx = b_idx
            self.second_best_b_similarity = b_idx_total_similarity

    def set_to_fully_measured(self):
        self.is_fully_measured = True

        # We sort so last = best as calling pop() on a list is O(1)
        # We negate the index here, so that the sorting is correct if the
        # similarities of two b's are the same (lowest index last)
        self._sorted_b_similarity_with_idx_pairs = sorted(
                ((s, -i) for i, s in enumerate(self.b_idx_to_similarity)))

    def replace_best(self):
        if not self._sorted_b_similarity_with_idx_pairs:
            return

        self._sorted_b_similarity_with_idx_pairs.pop()
        if not self._sorted_b_similarity_with_idx_pairs:
            # None left, which means all others a's have better values
            # than this one. As a result, this a will stay alone :(
            self.best_b_idx = -1
            self.best_b_similarity = float('-inf')
            return

        sim, idx = self._sorted_b_similarity_with_idx_pairs[-1]
        self.best_b_idx = -idx
        self.best_b_similarity = sim


class ObjectListMatcher(Generic[T]):
    """
    Utility class that compares the objects of two lists (all the same type), and finds
    the best matches. What is considered a good match depends on the supplied mapping,
    which maps "attribute getter" functions to their weight.

    Weights are normalized, so you can use values > 1.

    A specific getter has to return objects of only one of these types:
    - Real number (e.g. int or float) - compared by 1 - abs(delta) / max_delta
    - Other non-Sequence - converted to str which is a Sequence and then..
    - Sequence - compared using difflib.SequenceMatcher

    The problem this solves is called the "Assignment problem".

    Note that this class will not necessarily call every attribute function and thus
    not use its weight in the calculation, as it will avoid doing unnecessary
    calculations when the current best match for an element is undefeatable.

    For example, let's say we have an attribute x with weight 0.8 and an attribute y
    with weight 0.2. If, after checking the similarity on attribute x with all items,
    the highest similarity is 0.8 (it was equal to the compared item) and the second
    highest has a similarity of 0.5, then we won't check attribute y at all, as the
    second best cannot possibly win with the remaining weight (0.5 + 0.2 < 0.8)."""

    _matcher: SequenceMatcher
    _attr_with_weight: List[Tuple[Callable[[T], Any], float]]
    similarity_matrix: List[List[float]]
    _b_idx_to_a_match_data: List[Optional[_MatchData]]

    def __init__(self, attr_to_weight: AttributeGetterToWeight):
        self.update_attr_to_weights(attr_to_weight)
        self._matcher = SequenceMatcher()
        self.should_store_similarity_matrix = False
        """Whether or not to store the similarity_matrix."""

        self.similarity_matrix = []
        """This will only be populated if should_store_similarity_matrix is True, and
        then every time get_indices is called.
        It's a matrix that has the same number of elements as a_items. Each of those
        lists has the same number of elements as b_items. Those elements represent how
        similar an a item is to each b item. So matrix[a_idx][b_idx] gives you the
        similarity between the a item and b item at those indices."""

        self.minimum_similarity = 0
        """A value in the range [0, 1] that defines what similarity is required to be a
        valid match. Setting this to a reasonable value will speed up the calculation
        as low-quality matches will be discarded before a match conflict can even arise. 
        This has to be carefully chosen with regard to the weights, as this class will
        not necessarily incorporate all (but the largest) weights in the score.
        So, if you set this to 0.8, but your largest weight is 0.5, it's possible that
        a match will almost never be discarded. This can be fine, of course."""

        # This has not been tested heavily, so there might be some bugs!
        self.lock_in_if_similarity_first_above = 1  # FIXME: test this more
        """If the similarity is above this value, we lock it in as the best match.
        Improves performance by removing alternatives from all following elements."""

    @classmethod
    def for_sequence(cls, weights: Sequence[Real]):
        """Creates a matcher where itemgetter(n) is mapped to weight_list[n]"""
        attr_to_weight = {itemgetter(n): w for n, w in enumerate(weights)}
        return ObjectListMatcher(attr_to_weight)

    @classmethod
    def for_one_attr(cls, attr: AttributeGetter):
        """Creates a matcher where a single attribute of the objects are compared."""
        return ObjectListMatcher({attr: 1})

    @classmethod
    def of_identity(cls):
        """Creates a matcher where only the objects themselves are compared."""
        return cls.for_one_attr((lambda i: i))

    def update_attr_to_weights(self, attr_to_weight: AttributeGetterToWeight):
        if not attr_to_weight:
            raise ValueError("there must be at least one weight")

        # normalize
        weight_sum = sum(attr_to_weight.values())

        self._attr_with_weight = []
        for attr, weight in attr_to_weight.items():
            if weight <= 0:
                raise ValueError("weights <= 0 are not allowed")

            self._attr_with_weight.append((attr, weight / weight_sum))

        # from largest to smallest weight
        self._attr_with_weight.sort(key=lambda i: i[1], reverse=True)

        weight_left = 1.0
        self._attr_to_weight_left = []
        for _, weight in self._attr_with_weight:
            self._attr_to_weight_left.append(weight_left)
            weight_left -= weight

    def get_indices(self, a_items: List[T], b_items: List[T]) -> List[int]:
        """
        Returns the indices of b ordered so that they match elements in a.

        Size of a_items and b_items can differ. If there are more a_items than
        there are b_items, -1 is used if no match could be assigned to an a.
        As a result, the returned list always has the size of a_items.

        In terms of performance, it's preferable to supply the smaller list as a_items.
        """
        if not b_items:
            return [-1 for _ in a_items]

        self._b_items = list(enumerate(b_items))
        b_size = len(b_items)

        self._b_idx_to_a_match_data = [None for _ in range(b_size)]
        self._a_idx_to_match_data = []

        for a_idx, a in enumerate(a_items):
            match_data = _MatchData(a_idx, a, b_size)
            self._a_idx_to_match_data.append(match_data)

            self._measure_similarity_to_find_best_b_match(match_data)

            if match_data.best_b_similarity < self.minimum_similarity:
                match_data.best_b_idx = -1
            elif match_data.found_best:
                self._b_idx_to_a_match_data[match_data.best_b_idx] = match_data
            else:
                self._handle_conflicts_if_any(match_data)
            pass

        result = [md.best_b_idx for md in self._a_idx_to_match_data]

        if self.should_store_similarity_matrix:
            matrix = [md.b_idx_to_similarity for md in
                      self._a_idx_to_match_data]
            self.similarity_matrix = matrix

        # cleanup
        del self._b_items
        del self._b_idx_to_a_match_data
        del self._a_idx_to_match_data

        return result

    def _handle_conflicts_if_any(self, a1_match_data):
        while True:
            best_b_idx = a1_match_data.best_b_idx
            if best_b_idx == -1:
                # a1 has no matches left or could not find a match
                return

            a2_match_data = self._b_idx_to_a_match_data[best_b_idx]
            if a2_match_data is None:
                self._b_idx_to_a_match_data[best_b_idx] = a1_match_data
                return

            # We have found a conflict and will now solve it.
            a1_match_data = self._get_worse_match_data(a1_match_data,
                                                       a2_match_data)

    def _get_worse_match_data(self, a1_match_data, a2_match_data):
        # b is matched to a previous a (a2), so we have to find a better match
        self._finish_similarity_measures(a1_match_data)
        
        if a2_match_data.found_best:
            a1_match_data.replace_best()
            # still need to find a better match for a1

            return a1_match_data
        
        self._finish_similarity_measures(a2_match_data)

        # As the index of a1 will almost always be larger than a2, we use <=
        # here, since in case they're equal in terms of similarity, we want to
        # give some weight to the current order of b (index 0 preferred to 1).
        if a1_match_data.best_b_similarity <= a2_match_data.best_b_similarity:
            a1_match_data.replace_best()

            # still need to find a better match for a1
            return a1_match_data
        else:
            # a1 is better so replace a2 in map
            best_b_idx = a1_match_data.best_b_idx
            self._b_idx_to_a_match_data[best_b_idx] = a1_match_data

            a2_match_data.replace_best()

            # we need to find a new match for a2
            return a2_match_data

    def _finish_similarity_measures(self, a_match_data):
        """Only if this was called, is match data full measured and only then
        can match_data.replace_best() be called."""
        if a_match_data.is_fully_measured:
            return

        # figure out total similarity (without stopping) if we didn't
        self._measure_similarity_to_find_best_b_match(a_match_data)
        a_match_data.set_to_fully_measured()

    def _measure_similarity_to_find_best_b_match(self, a_match_data):
        continue_attr_idx = a_match_data.continue_attr_index
        can_stop = continue_attr_idx == 0
        attr_size = len(self._attr_with_weight)

        for attr_idx in range(continue_attr_idx, attr_size):
            if a_match_data.found_best:
                a_match_data.continue_attr_index = attr_size
                return

            # stop if one has more similarity than is possible for the rest
            if can_stop and self._is_max_similarity_undefeatable(attr_idx,
                                                                 a_match_data):
                a_match_data.continue_attr_index = attr_idx
                return

            self._measure_similarity_for_attr(attr_idx, a_match_data)

        a_match_data.continue_attr_index = attr_size

    def _is_max_similarity_undefeatable(self, attr_idx, a_match_data):
        # Must only be called at the start of the loop.
        # We need a second best, so we can check if they have any chance.
        if a_match_data.second_best_b_idx < 0:
            return False

        # Any similarity has to be in [0, 1], so the following is the maximum
        # similarity that could be achieved with the remaining attr / weights
        optimal_second_best_similarity = self._attr_to_weight_left[attr_idx]

        # Now we add the second best similarity, since we want to know if it's
        # even possible for the second best to win against the current best
        optimal_second_best_similarity += a_match_data.second_best_b_similarity

        return optimal_second_best_similarity < a_match_data.best_b_similarity

    def _measure_similarity_for_attr(self, attr_idx, a_match_data):
        get_attr, weight = self._attr_with_weight[attr_idx]
        a_attr = get_attr(a_match_data.a_value)

        # isinstance does not work with Union, so we need to use a tuple here
        if isinstance(a_attr, SUPPORTED_NUMBER_TYPES):
            self._add_number_similarity(a_match_data, a_attr, get_attr, weight)
            return

        if not isinstance(a_attr, Sequence):
            a_attr = str(a_attr)

            def get_attr(obj, original_get_attr=get_attr):
                return str(original_get_attr(obj))

            # replace it so we don't have to do this again for this attr_idx
            self._attr_with_weight[attr_idx] = (get_attr, weight)

        self._add_sequence_similarity(a_match_data, a_attr, get_attr, weight)

    def _add_number_similarity(self, a_match_data, a_attr, get_attr, weight):
        deltas = [abs(get_attr(b) - a_attr) for _, b in self._b_items]
        max_delta = max(deltas)
        if max_delta == 0:
            if a_match_data.best_b_idx == -1:
                # We try to set a match here manually to avoid the situation where
                # nothing is matched to a and -1 returned just because all are the same.
                # In all other cases MatchData's add_similarity takes care of this.
                for b_idx, match_data in enumerate(
                        self._b_idx_to_a_match_data):
                    # find the first b index that's not matched to an a element
                    if match_data is None:
                        a_match_data.best_b_idx = b_idx
                        a_match_data.best_b_similarity = 0
                        break

            # no delta, so all the same and no change in similarity
            return  # also let's avoid division by zero

        for b_idx, delta in enumerate(deltas):
            # if delta is small relative to max, similarity is higher
            # for example, if delta is 0, b_attr is the same as a_attr
            similarity = weight * (1 - delta / max_delta)
            a_match_data.add_similarity(b_idx, similarity)

    def _add_sequence_similarity(self, a_match_data, a_attr, get_attr, weight):
        matcher = self._matcher
        if a_match_data.found_best:
            return

        # set_seq2 is used here as it caches information (contrary to 1)
        matcher.set_seq2(a_attr)

        lock_in_min = self.lock_in_if_similarity_first_above

        b_items = self._b_items

        for i in range(len(b_items)):
            b_idx, b = b_items[i]
            b_attr = get_attr(b)

            matcher.set_seq1(b_attr)

            a_match_data.add_similarity(b_idx, weight * matcher.ratio())

            if (a_match_data.best_b_idx == b_idx and  #
                    a_match_data.best_b_similarity > lock_in_min and
                    a_attr and b_attr):
                del b_items[i]
                a_match_data.found_best = True
                return
