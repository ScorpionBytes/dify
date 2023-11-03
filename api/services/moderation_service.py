from typing import Union

from models.model import AppModelConfig, App, Account, EndUser
from core.moderation.factory import ModerationFactory
from extensions.ext_database import db

class ModerationService:

    def moderation_for_outputs(self, app_model: App, user: Union[Account , EndUser], text: str) -> dict:
        app_model_config: AppModelConfig = None

        app_model_config = db.session.query(AppModelConfig).filter(AppModelConfig.id == app_model.app_model_config_id).first()

        if not app_model_config:
            raise ValueError("app model config not found")
        
        name = app_model_config.sensitive_word_avoidance_dict['type']
        config = app_model_config.sensitive_word_avoidance_dict['configs']

        moderation = ModerationFactory(name, user.tenant_id, config)
        return moderation.moderation_for_outputs(text).dict()