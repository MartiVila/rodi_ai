from QConfig import QConfig
from Station_Translator import StationTranslator
from Train_Agent import TrainAgent

# Suppose environment says there are 3 trains, 4 stations, and 2 actions.
translator = StationTranslator(n_trains=3, n_nodes=4)
config = QConfig(alpha=0.7, gamma=0.9, epsilon=0.9, epsilon_decay=0.05)

agent = TrainAgent(
    translator=translator,
    n_actions=2,
    config=config,
    actions=(0, 1),  # 0 = brake, 1 = accelerate
)

# Inside your training loop, given env data:
train_id, node_id = 0, 2
state_id = translator.encode(train_id, node_id)
action_idx = agent.evaluate_actions(state_id)

# You send the concrete action to the env (e.g. brake/accelerate),
# get reward and next observation back, then:
next_state_id = translator.encode(next_train_id, next_node_id)

agent.learn(state_id, action_idx, reward, next_state_id, done)
agent.decay_epsilon()  # e.g. at episode end
