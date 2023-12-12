import logging
import os
import time
from abc import abstractmethod
from typing import Optional, Generator, Union, List

from transformers import GPT2Tokenizer

from core.model_runtime.callbacks.base_callback import Callback
from core.model_runtime.callbacks.logging_callback import LoggingCallback
from core.model_runtime.entities.message_entities import PromptMessage, PromptMessageTool, AssistantPromptMessage
from core.model_runtime.entities.model_entities import ModelPropertyKey, PriceType, ParameterType, ParameterRule
from core.model_runtime.entities.llm_entities import LLMResult, LLMMode, LLMUsage, \
    LLMResultChunk, LLMResultChunkDelta
from core.model_runtime.model_providers.__base.ai_model import AIModel


logger = logging.getLogger(__name__)


class LargeLanguageModel(AIModel):
    """
    Model class for large language model.
    """

    def invoke(self, model: str, credentials: dict,
               prompt_messages: list[PromptMessage], model_parameters: Optional[dict] = None,
               tools: Optional[list[PromptMessageTool]] = None, stop: Optional[List[str]] = None,
               stream: bool = True, user: Optional[str] = None, callbacks: list[Callback] = None) \
            -> Union[LLMResult, Generator]:
        """
        Invoke large language model

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :param callbacks: callbacks
        :return: full response or stream response chunk generator result
        """
        # validate and filter model parameters
        if model_parameters is None:
            model_parameters = {}

        model_parameters = self._validate_and_filter_model_parameters(model, model_parameters)

        self.started_at = time.perf_counter()

        callbacks = callbacks or []

        if bool(os.environ.get("DEBUG")):
            callbacks.append(LoggingCallback())

        # trigger before invoke callbacks
        self._trigger_before_invoke_callbacks(
            model=model,
            credentials=credentials,
            prompt_messages=prompt_messages,
            model_parameters=model_parameters,
            tools=tools,
            stop=stop,
            stream=stream,
            user=user,
            callbacks=callbacks
        )

        try:
            result = self._invoke(model, credentials, prompt_messages, model_parameters, tools, stop, stream, user)
        except Exception as e:
            self._trigger_invoke_error_callbacks(
                model=model,
                ex=e,
                credentials=credentials,
                prompt_messages=prompt_messages,
                model_parameters=model_parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                user=user,
                callbacks=callbacks
            )

            raise self._transform_invoke_error(e)

        if stream and isinstance(result, Generator):
            return self._invoke_result_generator(
                model=model,
                result=result,
                credentials=credentials,
                prompt_messages=prompt_messages,
                model_parameters=model_parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                user=user,
                callbacks=callbacks
            )
        else:
            self._trigger_after_invoke_callbacks(
                model=model,
                result=result,
                credentials=credentials,
                prompt_messages=prompt_messages,
                model_parameters=model_parameters,
                tools=tools,
                stop=stop,
                stream=stream,
                user=user,
                callbacks=callbacks
            )

        return result

    def _invoke_result_generator(self, model: str, result: Generator, credentials: dict,
                                 prompt_messages: list[PromptMessage], model_parameters: dict,
                                 tools: Optional[list[PromptMessageTool]] = None,
                                 stop: Optional[List[str]] = None, stream: bool = True,
                                 user: Optional[str] = None, callbacks: list[Callback] = None) -> Generator:
        """
        Invoke result generator

        :param result: result generator
        :return: result generator
        """
        prompt_message = AssistantPromptMessage(
            content=""
        )
        usage = None
        system_fingerprint = None
        real_model = model

        for chunk in result:
            try:
                yield chunk

                self._trigger_new_chunk_callbacks(
                    chunk=chunk,
                    model=model,
                    credentials=credentials,
                    prompt_messages=prompt_messages,
                    model_parameters=model_parameters,
                    tools=tools,
                    stop=stop,
                    stream=stream,
                    user=user,
                    callbacks=callbacks
                )

                prompt_message.content += chunk.delta.message.content
                real_model = chunk.model
                if chunk.delta.usage:
                    usage = chunk.delta.usage

                if chunk.system_fingerprint:
                    system_fingerprint = chunk.system_fingerprint
            except Exception as e:
                raise self._transform_invoke_error(e)

        self._trigger_after_invoke_callbacks(
            model=model,
            result=LLMResult(
                model=real_model,
                message=prompt_message,
                usage=usage,
                system_fingerprint=system_fingerprint
            ),
            credentials=credentials,
            prompt_messages=prompt_messages,
            model_parameters=model_parameters,
            tools=tools,
            stop=stop,
            stream=stream,
            user=user,
            callbacks=callbacks
        )

    @abstractmethod
    def _invoke(self, model: str, credentials: dict,
                prompt_messages: list[PromptMessage], model_parameters: dict,
                tools: Optional[list[PromptMessageTool]] = None, stop: Optional[List[str]] = None,
                stream: bool = True, user: Optional[str] = None) \
            -> Union[LLMResult, Generator]:
        """
        Invoke large language model

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :return: full response or stream response chunk generator result
        """
        raise NotImplementedError

    @abstractmethod
    def get_num_tokens(self, model: str, prompt_messages: list[PromptMessage],
                       tools: Optional[list[PromptMessageTool]] = None) -> int:
        """
        Get number of tokens for given prompt messages

        :param model:
        :param prompt_messages:
        :param tools: tools for tool calling
        :return:
        """
        raise NotImplementedError

    def _get_num_tokens_by_gpt2(self, text: str) -> int:
        """
        Get number of tokens for given prompt messages by gpt2
        Some provider models do not provide an interface for obtaining the number of tokens.
        Here, the gpt2 tokenizer is used to calculate the number of tokens.
        This method can be executed offline, and the gpt2 tokenizer has been cached in the project.

        :param text: plain text of prompt. You need to convert the original message to plain text
        :return: number of tokens
        """
        base_path = os.path.abspath(__file__)
        gpt2_tokenizer_path = os.path.join(os.path.join(os.path.dirname(base_path), 'tokenizers'), 'gpt2')
        tokenizer = GPT2Tokenizer.from_pretrained(gpt2_tokenizer_path)
        tokens = tokenizer.encode(text)
        return len(tokens)

    def _llm_result_to_stream(self, result: LLMResult) -> Generator:
        """
        Transform llm result to stream

        :param result: llm result
        :return: stream
        """
        index = 0

        tool_calls = result.message.tool_calls

        for word in result.message.content:
            assistant_prompt_message = AssistantPromptMessage(
                content=word,
                tool_calls=tool_calls if index == (len(result.message.content) - 1) else []
            )

            yield LLMResultChunk(
                model=result.model,
                system_fingerprint=result.system_fingerprint,
                delta=LLMResultChunkDelta(
                    index=index,
                    message=assistant_prompt_message,
                )
            )

            index += 1
            time.sleep(0.01)

    def get_parameter_rules(self, model: str, credentials: dict) -> list[ParameterRule]:
        """
        Get parameter rules

        :param model: model name
        :param credentials: model credentials
        :return: parameter rules
        """
        # get predefined models (predefined_models)
        models = self.predefined_models()

        # get remote models from remote api
        remote_models = self.remote_models(credentials)

        if remote_models:
            # merge predefined_models and remote_models
            predefined_model_ids = [model.model for model in models]
            for remote_model in remote_models:
                if remote_model.model not in predefined_model_ids:
                    models.append(remote_model)

        model_map = {model.model: model for model in models}
        if model in model_map:
            return model_map[model].parameter_rules

        return self.get_customizable_model_parameter_rules(model, credentials)

    def get_customizable_model_parameter_rules(self, model: str, credentials: dict) -> list[ParameterRule]:
        """
        Get customizable model parameter rules

        :param model: model name
        :param credentials: model credentials
        :return: parameter rules
        """
        return []

    def get_model_mode(self, model: str) -> LLMMode:
        """
        Get model mode

        :param model: model name
        :return: model mode
        """
        model_schema = self.get_predefined_model_schema(model)

        mode = LLMMode.CHAT
        if model_schema and model_schema.model_properties.get(ModelPropertyKey.MODE):
            mode = LLMMode.value_of(model_schema.model_properties[ModelPropertyKey.MODE])

        return mode

    def _calc_response_usage(self, model: str, prompt_tokens: int, completion_tokens: int) -> LLMUsage:
        """
        Calculate response usage

        :param model: model name
        :param prompt_tokens: prompt tokens
        :param completion_tokens: completion tokens
        :return: usage
        """
        # get prompt price info
        prompt_price_info = self.get_price(
            model=model,
            price_type=PriceType.INPUT,
            tokens=prompt_tokens
        )

        # get completion price info
        completion_price_info = self.get_price(
            model=model,
            price_type=PriceType.OUTPUT,
            tokens=completion_tokens
        )

        # transform usage
        usage = LLMUsage(
            prompt_tokens=prompt_tokens,
            prompt_unit_price=prompt_price_info.unit_price,
            prompt_price_unit=prompt_price_info.unit,
            prompt_price=prompt_price_info.total_amount,
            completion_tokens=completion_tokens,
            completion_unit_price=completion_price_info.unit_price,
            completion_price_unit=completion_price_info.unit,
            completion_price=completion_price_info.total_amount,
            total_tokens=prompt_tokens + completion_tokens,
            total_price=prompt_price_info.total_amount + completion_price_info.total_amount,
            currency=prompt_price_info.currency,
            latency=time.perf_counter() - self.started_at
        )

        return usage

    def _trigger_before_invoke_callbacks(self, model: str, credentials: dict,
                                         prompt_messages: list[PromptMessage], model_parameters: dict,
                                         tools: Optional[list[PromptMessageTool]] = None,
                                         stop: Optional[List[str]] = None, stream: bool = True,
                                         user: Optional[str] = None, callbacks: list[Callback] = None) -> None:
        """
        Trigger before invoke callbacks

        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :param callbacks: callbacks
        """
        if callbacks:
            for callback in callbacks:
                try:
                    callback.on_before_invoke(
                        llm_instance=self,
                        model=model,
                        credentials=credentials,
                        prompt_messages=prompt_messages,
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        user=user
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning(f"Callback {callback.__class__.__name__} on_before_invoke failed with error {e}")

    def _trigger_new_chunk_callbacks(self, chunk: LLMResultChunk, model: str, credentials: dict,
                                     prompt_messages: list[PromptMessage], model_parameters: dict,
                                     tools: Optional[list[PromptMessageTool]] = None,
                                     stop: Optional[List[str]] = None, stream: bool = True,
                                     user: Optional[str] = None, callbacks: list[Callback] = None) -> None:
        """
        Trigger new chunk callbacks

        :param chunk: chunk
        :param model: model name
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        """
        if callbacks:
            for callback in callbacks:
                try:
                    callback.on_new_chunk(
                        llm_instance=self,
                        chunk=chunk,
                        model=model,
                        credentials=credentials,
                        prompt_messages=prompt_messages,
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        user=user
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning(f"Callback {callback.__class__.__name__} on_new_chunk failed with error {e}")

    def _trigger_after_invoke_callbacks(self, model: str, result: LLMResult, credentials: dict,
                                        prompt_messages: list[PromptMessage], model_parameters: dict,
                                        tools: Optional[list[PromptMessageTool]] = None,
                                        stop: Optional[List[str]] = None, stream: bool = True,
                                        user: Optional[str] = None, callbacks: list[Callback] = None) -> None:
        """
        Trigger after invoke callbacks

        :param model: model name
        :param result: result
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :param callbacks: callbacks
        """
        if callbacks:
            for callback in callbacks:
                try:
                    callback.on_after_invoke(
                        llm_instance=self,
                        result=result,
                        model=model,
                        credentials=credentials,
                        prompt_messages=prompt_messages,
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        user=user
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning(f"Callback {callback.__class__.__name__} on_after_invoke failed with error {e}")

    def _trigger_invoke_error_callbacks(self, model: str, ex: Exception, credentials: dict,
                                        prompt_messages: list[PromptMessage], model_parameters: dict,
                                        tools: Optional[list[PromptMessageTool]] = None,
                                        stop: Optional[List[str]] = None, stream: bool = True,
                                        user: Optional[str] = None, callbacks: list[Callback] = None) -> None:
        """
        Trigger invoke error callbacks

        :param model: model name
        :param ex: exception
        :param credentials: model credentials
        :param prompt_messages: prompt messages
        :param model_parameters: model parameters
        :param tools: tools for tool calling
        :param stop: stop words
        :param stream: is stream response
        :param user: unique user id
        :param callbacks: callbacks
        """
        if callbacks:
            for callback in callbacks:
                try:
                    callback.on_invoke_error(
                        llm_instance=self,
                        ex=ex,
                        model=model,
                        credentials=credentials,
                        prompt_messages=prompt_messages,
                        model_parameters=model_parameters,
                        tools=tools,
                        stop=stop,
                        stream=stream,
                        user=user
                    )
                except Exception as e:
                    if callback.raise_error:
                        raise e
                    else:
                        logger.warning(f"Callback {callback.__class__.__name__} on_invoke_error failed with error {e}")

    def _validate_and_filter_model_parameters(self, model: str, model_parameters: dict) -> dict:
        """
        Validate model parameters

        :param model: model name
        :param model_parameters: model parameters
        :return:
        """
        model_schema = self.get_predefined_model_schema(model)
        if not model_schema:
            return model_parameters

        parameter_rules = model_schema.parameter_rules

        # validate model parameters
        filtered_model_parameters = {}
        for parameter_rule in parameter_rules:
            parameter_name = parameter_rule.name
            parameter_value = model_parameters.get(parameter_name)
            if parameter_value is None:
                if parameter_rule.required:
                    if parameter_rule.default_value is not None:
                        filtered_model_parameters[parameter_name] = parameter_rule.default_value
                        continue
                    else:
                        raise ValueError(f"Model Parameter {parameter_name} is required.")
                else:
                    continue

            # validate parameter value type
            if parameter_rule.type == ParameterType.INT:
                if not isinstance(parameter_value, int):
                    raise ValueError(f"Model Parameter {parameter_name} should be int.")

                # validate parameter value range
                if parameter_rule.min is not None and parameter_value < parameter_rule.min:
                    raise ValueError(
                        f"Model Parameter {parameter_name} should be greater than or equal to {parameter_rule.min}.")

                if parameter_rule.max is not None and parameter_value > parameter_rule.max:
                    raise ValueError(
                        f"Model Parameter {parameter_name} should be less than or equal to {parameter_rule.max}.")
            elif parameter_rule.type == ParameterType.FLOAT:
                if not isinstance(parameter_value, (float, int)):
                    raise ValueError(f"Model Parameter {parameter_name} should be float.")

                # validate parameter value precision
                if parameter_rule.precision is not None:
                    if parameter_rule.precision == 0:
                        if parameter_value != int(parameter_value):
                            raise ValueError(f"Model Parameter {parameter_name} should be int.")
                    else:
                        if parameter_value != round(parameter_value, parameter_rule.precision):
                            raise ValueError(
                                f"Model Parameter {parameter_name} should be round to {parameter_rule.precision} decimal places.")

                # validate parameter value range
                if parameter_rule.min is not None and parameter_value < parameter_rule.min:
                    raise ValueError(
                        f"Model Parameter {parameter_name} should be greater than or equal to {parameter_rule.min}.")

                if parameter_rule.max is not None and parameter_value > parameter_rule.max:
                    raise ValueError(
                        f"Model Parameter {parameter_name} should be less than or equal to {parameter_rule.max}.")
            elif parameter_rule.type == ParameterType.BOOLEAN:
                if not isinstance(parameter_value, bool):
                    raise ValueError(f"Model Parameter {parameter_name} should be bool.")
            elif parameter_rule.type == ParameterType.STRING:
                if not isinstance(parameter_value, str):
                    raise ValueError(f"Model Parameter {parameter_name} should be string.")

                # validate options
                if parameter_rule.options and parameter_value not in parameter_rule.options:
                    raise ValueError(f"Model Parameter {parameter_name} should be one of {parameter_rule.options}.")
            else:
                raise ValueError(f"Model Parameter {parameter_name} type {parameter_rule.type} is not supported.")

            # change parameter name to alias if alias is present
            if parameter_rule.alias is not None and parameter_rule.alias != parameter_name:
                filtered_model_parameters[parameter_rule.alias] = parameter_value
            else:
                filtered_model_parameters[parameter_name] = parameter_value

        return filtered_model_parameters