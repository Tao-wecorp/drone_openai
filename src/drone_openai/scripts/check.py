from stable_baselines3.common.env_checker import check_env
from env import GoLeftEnv
env = GoLeftEnv()

check_env(env, warn=False)