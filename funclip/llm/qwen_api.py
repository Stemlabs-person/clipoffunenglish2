import dashscope
from dashscope import Generation


def call_qwen_model(key=None, 
                    model="qwen_plus", 
                    user_content="How do you braise beef brisket with tomatoes?",
                    system_content=None):
    dashscope.api_key = key
    if system_content is not None and len(system_content.strip()):
        messages = [
            {'role': 'system', 'content': system_content},
            {'role': 'user', 'content': user_content}
      ]
    else:
        messages = [
            {'role': 'user', 'content': user_content}
      ]
    responses = Generation.call(model,
                                messages=messages,
                                result_format='message',  # set output format to 'message'
                                stream=False, # set output mode to streaming
                                incremental_output=False  # incremental streaming output
                                )
    print(responses)
    return responses['output']['choices'][0]['message']['content']


if __name__ == '__main__':
    call_qwen_model('YOUR_BAILIAN_APIKEY')