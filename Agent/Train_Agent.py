import random
import numpy as np

from QConfig import QConfig
from QTable import QTable
from Station_Translator import StationTranslator


class TrainAgent:
    """
    Q-learning agent that controls a single train (or more, depending on how
    StationTranslator encodes the state).

    It is environment-agnostic: it only works with integer state ids and
    action indices.
    """

    def __init__(
        self,
        translator: StationTranslator,
        n_actions: int,
        config: QConfig | None = None,
        actions: tuple[int, ...] | None = None,
    ):
        self.translator = translator
        self.n_actions = n_actions
        self.config = config or QConfig()

        # actions can be domain-specific codes if you want
        # e.g. 0 = brake, 1 = accelerate
        self.actions = actions if actions is not None else tuple(range(n_actions))

        # create Q-table with as many states as translator encodes
        self.q_table = QTable(self.translator.n_states, self.n_actions)

    def evaluate_actions(self, state_id: int) -> int:
        """
        Decide an action index given a discrete state id.
        """
        return self._policy(state_id)

    def _policy(self, state_id: int) -> int:
        """
        Epsilon-greedy policy on the Q-table.
        """
        if random.random() < self.config.epsilon:
            return self._explore()
        return self._greedy_action(state_id)

    def _explore(self) -> int:
        """
        Return a random action index.
        """
        return random.randrange(self.n_actions)

    def _greedy_action(self, state_id: int) -> int:
        """
        Return argmax_a Q(state, a).
        """
        q_row = self.q_table.get_row(state_id)
        return int(np.argmax(q_row))

    def learn(
        self,
        state_id: int,
        action_idx: int,
        reward: float,
        next_state_id: int,
        done: bool,
    ) -> None:
        """
        One Q-learning update step.
        """
        self.q_table.update(
            state=state_id,
            action=action_idx,
            reward=reward,
            next_state=next_state_id,
            done=done,
            alpha=self.config.alpha,
            gamma=self.config.gamma,
        )

    def decay_epsilon(self) -> None:
        """
        Deterministic epsilon decay after an episode (or after N steps).
        """
        new_eps = self.config.epsilon - self.config.epsilon_decay
        self.config.epsilon = max(self.config.min_epsilon, new_eps)
