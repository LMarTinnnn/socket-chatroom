import config_override
from config_default import configs


def merge(default, override):
    merged_dict = dict()
    for k, v in default.items():
        if k in override:
            if isinstance(v, dict):
                merged_dict[k] = merge(v, override[k])
            else:
                merged_dict[k] = v
        else:
            merged_dict[k] = v
    return merged_dict


override_config = config_override.configs
configs = merge(configs, override_config)
