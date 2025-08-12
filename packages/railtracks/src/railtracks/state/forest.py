from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Dict, Generic, Iterable, List, Optional, Tuple, TypeVar

from typing_extensions import Self

from railtracks.utils.profiling import Stamp


def get_all_open_heads(
    all_linked_objects: Iterable[T], active_pointers: Iterable[T]
) -> Tuple[List[T], List[T]]:
    # the first step is to traverse the active pointers that we can then search for the extras after
    removed_normal_pathway = set(all_linked_objects)
    for l_o in active_pointers:
        while l_o.parent is not None:
            removed_normal_pathway.remove(l_o)
            l_o = l_o.parent

        removed_normal_pathway.remove(l_o)

    # now that we just have the dead ones we can traverse backwards
    dead_heads = []

    for identifier in {x.identifier for x in removed_normal_pathway}:
        relevant_nodes = {
            x for x in removed_normal_pathway if x.identifier == identifier
        }

        parents = {x.parent for x in relevant_nodes}
        for n in relevant_nodes:
            if n not in parents:
                dead_heads.append(n)
                break

    return list(active_pointers), dead_heads


@dataclass(frozen=True)
class AbstractLinkedObject:
    """
    A simple base class that can be subclassed to create your own objects with custom parameters that will work out
    of the box with the `Forest` object.
    """

    identifier: str
    stamp: Stamp
    parent: Optional[Self]


T = TypeVar("T", bound=AbstractLinkedObject)


class Forest(Generic[T]):
    """
    A general base class for any heap object. These heap objects have a non-intuitive structure. A common use case of
    a type like this is used to record history of some object. By linking together objects with the same identifier, you
    can create a history of immutable objects that can be accessed at any point in time. You can also build out any of
    your own desired functionality of the object by subclassing `Forest`.

    The general principle of the object is you can add any subclass of `AbstractLinkedObject` to the heap. The heap will
    track any object with identical identifiers as connected objects. Any object which you add that already exists in
    the heap (and by that I mean an object with the same identifier) must have a parent in the graph that matches that
    object. Once you have added that new object it is now the object that you can access from the heap. Conveniently
    because all `T` are immutable, you can pass around the objects without worry of pass by reference bugs.
    """

    def __init__(self, heap: Dict[str, T] | None = None):
        if heap is not None:
            self._heap = heap
            self._full_data = self._create_full_data_from_heap(heap)
        else:
            self._heap: Dict[str, T] = {}
            self._full_data: List[T] = []
        self._lock = threading.RLock()

    @classmethod
    def _create_full_data_from_heap(cls, heap: Dict[str, T]):
        """
        Recursively expands the heap object to create a full data list of all objects in the heap.
        """
        full_data = []
        for item in heap.values():
            curr_ref = item
            while True:
                full_data.append(curr_ref)

                curr_ref = curr_ref.parent
                if curr_ref is None:
                    break

        return full_data

    def heap(self):
        """
        Returns a passed by value dictionary of all the data in the heap.

        NOTE: You can do whatever you please with this object, and it will not affect the inner workings of the object.
        """
        # note that all of the objects are immutable so we can do this without worry of pass by reference bugs

        return dict(self._heap)

    def full_data(self, at_step: int = None):
        """
        Returns a passed by value list of all the data in the heap.

        NOTE: You can do whatever you please with this object, and it will not affect the inner workings of the object.
        """
        if at_step is None:
            return list(self._full_data)
        return [x for x in self._full_data if x.stamp.step <= at_step]

    def __getitem__(self, identifier: str):
        """
        Collects the provided item from the heap with a matching identifier. This will be the most recent item of
        that identifier that you have added.

        To access previous elements of the same identifier, you must use the `parent` attribute of the object.

        Returns:
            T: The item with the given identifier if it exists in the heap
        Raises:
            TypeError: If the identifier is not a string
            KeyError: If the identifier is not in the heap
        """
        if not isinstance(identifier, str):
            raise TypeError(f"Expected a string but got {type(identifier)}")
        return self._heap[identifier]

    def __contains__(self, item: str):
        return item in self._heap

    def _update_heap(self, item: T):
        """
        A thread safe operation to add the given item to the heap. Note that there is some special requirements for the
        item you provide:
        1. If the `item.identifier` is already in the heap, then the one in the heap must be its parent
        2. If the `item.identifier` is not in the heap, then the `item.parent` must be `None`

        The item will be added to the heap and the full data list.

        After adding this object to the heap, you can access the one you added via its identifier.

        Args:
            item (T): The item to add to the heap
        """
        with self._lock:
            if item.identifier in self._heap:
                assert item.parent == self._heap[item.identifier], (
                    "The parent of the inserted item must be currently pointed to"
                )
                assert item.stamp.step > self._heap[item.identifier].stamp.step, (
                    "The step must be greater than the current"
                )
            else:
                assert item.parent is None, (
                    "The parent of an item not present in the heap must be None"
                )

            self._heap[item.identifier] = item
            self._full_data.append(item)

    def time_machine(self, step: int | None, item_list: Optional[List[str]] = None):
        """
        This function mutates the state of self such that all items you have provided are returned to state at the given
        step. If you have not provided any items it will be assumed that you want the entire heap to be returned to the
        given step.

        Note that it will include all items with the given step and less (it is inclusive of the step).

        If none of the items with the given ID are less than or equal to the given step, then the item will be removed.

        Args:
            step (int): The step to return the items to (inclusive of that step). If none then return the current state.
            item_list (Optional[List[str]]): The list of identifiers to return to the given step. If None, then all items
                will be returned to the given step. Note an empty list will mean that nothing will happen
        """
        if step is None:
            return self

        if item_list is None:
            item_list = list(self._heap.keys())

        for identifier in item_list:
            item = self._heap[identifier]
            while item is not None and item.stamp.step > step:
                item = item.parent
            if item is None:
                del self._heap[identifier]
            else:
                self._heap[identifier] = item

    def __getstate__(self):
        # we cannot serialize the _lock because it bricks things
        return {k: v for k, v in self.__dict__.items() if k != "_lock"}

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._lock = threading.RLock()
