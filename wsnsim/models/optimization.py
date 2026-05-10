import itertools
import json
from typing import Any, Dict, Iterator, List, Tuple

class ParameterGrid:
    """Generates all combinations of parameters from a dictionary of lists."""
    
    def __init__(self, param_dict: Dict[str, List[Any]]):
        self.param_dict = param_dict
        self.keys = list(param_dict.keys())
        self.values = list(param_dict.values())
        
    def __iter__(self) -> Iterator[Dict[str, Any]]:
        if not self.values:
            yield {}
            return
            
        for combination in itertools.product(*self.values):
            yield dict(zip(self.keys, combination))
            
    def __len__(self) -> int:
        if not self.values:
            return 0
        length = 1
        for val_list in self.values:
            length *= len(val_list)
        return length


class ParetoFilter:
    """Filters a set of solutions to find the Pareto optimal (non-dominated) set."""
    
    def __init__(self, directions: Tuple[str, ...]):
        """
        Args:
            directions: A tuple of strings 'min' or 'max' indicating the 
                        optimization direction for each objective.
        """
        self.directions = directions
        self.multipliers = tuple(1 if d == 'max' else -1 for d in directions)
        
    def _dominates(self, obj1: Tuple[float, ...], obj2: Tuple[float, ...]) -> bool:
        """Checks if obj1 dominates obj2."""
        if len(obj1) != len(obj2):
            raise ValueError("Objective tuples must have the same length.")
            
        strictly_better = False
        for o1, o2, mult in zip(obj1, obj2, self.multipliers):
            val1 = o1 * mult
            val2 = o2 * mult
            if val1 < val2:
                return False
            if val1 > val2:
                strictly_better = True
        return strictly_better

    def filter(self, solutions: List[Tuple[Any, Tuple[float, ...]]]) -> List[Tuple[Any, Tuple[float, ...]]]:
        """
        Filters the solutions to return only the Pareto-optimal ones.
        
        Args:
            solutions: A list of tuples (solution_id_or_data, objectives)
                       objectives must be a tuple of floats matching the length of directions.
        Returns:
            A list of Pareto-optimal solutions.
        """
        if not solutions:
            return []
            
        pareto_front = []
        for i, sol1 in enumerate(solutions):
            dominated = False
            for j, sol2 in enumerate(solutions):
                if i == j:
                    continue
                if self._dominates(sol2[1], sol1[1]):
                    dominated = True
                    break
            if not dominated:
                pareto_front.append(sol1)
                
        return pareto_front


class ConfigDumper:
    """Helper to dump configuration and results to JSON."""
    
    @staticmethod
    def dump(filepath: str, config: Dict[str, Any], results: Any) -> None:
        """Dumps config and results to a JSON file."""
        data = {
            "config": config,
            "results": results
        }
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, default=str)
