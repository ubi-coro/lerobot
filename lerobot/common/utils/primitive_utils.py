from abc import ABC, abstractmethod
from typing import Any, Dict
import numpy as np

from lerobot.common.robot_devices.control_configs import PrimitiveConfig, TransitionConfig


PRIMITIVE_REGISTRY = {
        "policy": PolicyPrimitive,
        "linear_interpolation": EELinearInterpolationPrimitive,
        "terminal": TerminalPrimitive
    }

CONDITION_REGISTRY = {
    "learnable": LearnableCondition,
    "close_to_point": PointCondition,
}


def mpn_control_loop(
        robot,
        primitives: list[PrimitiveConfig],
        transitions: list[TransitionConfig],
        initial_primitive: str | None = None,
        repeat_node=repeat_node
):
    assert len(primitives) > 0, "mpn_control_loop: MPN is empty"

    if initial_primitive is None:
        initial_primitive = primitives[0].name

    # initialize primitives and transitions
    primitives = {p.name: PRIMITIVE_REGISTRY[p.type](**p.params) for p in primitives}
    transitions = [
            (
                t.source,
                t.target,
                self.CONDITION_REGISTRY[t.condition_cls](t.params)
            )
            for t in transitions
        ]

    # set start primitive
    assert initial_primitive in primitives
    current_primitive = initial_primitive
    primitives[current_primitive].reset()

    # traverse mpn
    visited = set()
    while primitives[current_primitive] != TerminalPrimitive:
        visited.add(current_primitive)

        observation = robot.capture_observation()
        action = primitives[current_primitive].select_action(observation)
        robot.send_action(action)

        # check transitions
        has_targets = False
        for source, target, condition in transitions:
            if source == current_primitive and condition.is_triggered(observation):
                print(f"Transitioning: {source} → {target}")
                current_primitive = target
                primitives[current_primitive].reset()
            has_targets = True

        # break conditions
        if not has_targets or primitives[current_primitive] != TerminalPrimitive:
            print(f"mpn_control_loop: Reached terminal mode, stopping.")
            break

        if current_primitive in visited and not repeat_node:
            print(f"mpn_control_loop: Repeated node, stopping.")
            break

# Abstract Base Classes
class Primitive(ABC):
    @abstract_method
    def select_action(self, observation: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstract_method
    def reset(self):
        pass

class Condition(ABC):
    @abstract_method
    def is_triggered(self, observation: Dict[str, Any]) -> bool:
        pass

# Concrete Primitive Implementations
class PolicyPrimitive(Primitive):
    def __init__(self, policy_path: str):
        self.policy_path = policy_path
        self.policy = self._load_policy(policy_path)

    def _load_policy(self, path):
        print(f"Loading policy from: {path}")
        # Mocked policy loading logic (Replace with real model loading)
        return lambda obs: {"action": np.array([0.0, 0.1])}

    def select_action(self, observation):
        action = self.policy(observation)
        print(f"PolicyPrimitive action: {action}")
        return action

class EELinearInterpolationPrimitive(Primitive):
    def __init__(self, start_pose: list, end_pose: list, duration: float = 2.0):
        self.start_pose = np.array(start_pose)
        self.end_pose = np.array(end_pose)
        self.duration = duration
        self.elapsed = 0.0
        self.dt = 0.1  # simulation timestep, replace as needed

    def select_action(self, observation):
        t = min(self.elapsed / self.duration, 1.0)
        current_pose = (1 - t) * self.start_pose + t * self.end_pose
        self.elapsed += self.dt
        print(f"EELinearInterpolationPrimitive pose: {current_pose.tolist()}")
        return {"ee_pose": current_pose.tolist()}

class TerminalPrimitive(Primitive):
    def select_action(self, observation):
        print("TerminalPrimitive: no action")
        return {}

# Concrete Condition Implementations
class LearnableCondition(Condition):
    def __init__(self, classifier_path: str, threshold: float = 0.5):
        self.classifier_path = classifier_path
        self.threshold = threshold
        self.classifier = self._load_classifier(classifier_path)

    def _load_classifier(self, path):
        print(f"Loading classifier from: {path}")
        # Mocked classifier (Replace with actual classifier loading)
        return lambda obs: 0.7  # Example probability

    def is_triggered(self, observation):
        score = self.classifier(observation)
        triggered = score >= self.threshold
        print(f"LearnableCondition score: {score}, triggered: {triggered}")
        return triggered

class PointCondition(Condition):
    def __init__(self, target_point: list, threshold: float = 0.01):
        self.target_point = np.array(target_point)
        self.threshold = threshold

    def is_triggered(self, observation):
        current_point = np.array(observation.get("ee_position", [0, 0, 0]))
        distance = np.linalg.norm(current_point - self.target_point)
        triggered = distance <= self.threshold
        print(f"PointCondition distance: {distance}, triggered: {triggered}")
        return triggered




