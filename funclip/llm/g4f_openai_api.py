from g4f.client import Client

if __name__ == '__main__':
    from llm.demo_prompt import demo_prompt
    client = Client()
    response = client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello, what is your name?"}],
    )
    print(response.choices[0].message.content)
 

def g4f_openai_call(model="gpt-3.5-turbo", 
                    user_content="How do you braise beef brisket with tomatoes?",
                    system_content=None):
    client = Client()
    if system_content is not None and len(system_content.strip()):
        messages = [
            {'role': 'system', 'content': system_content},
            {'role': 'user', 'content': user_content}
      ]
    else:
        messages = [
            {'role': 'user', 'content': user_content}
      ]
    response = client.chat.completions.create(
        model=model,
        messages=messages,
    )
    return(response.choices[0].message.content)


def free_llm7_call(user_content="How do you braise beef brisket with tomatoes?",
                   system_content=None):
    """Free, keyless LLM call via g4f's LLM7 provider.

    Unlike g4f's default auto-provider (which now gates most models behind
    a "cake credits" proof-of-work/signup system - see g4f_openai_call),
    LLM7 works anonymously with no key and no signup. It only exposes one
    model, requested as "default".
    """
    from g4f.Provider import LLM7
    client = Client(provider=LLM7)
    if system_content is not None and len(system_content.strip()):
        messages = [
            {'role': 'system', 'content': system_content},
            {'role': 'user', 'content': user_content}
      ]
    else:
        messages = [
            {'role': 'user', 'content': user_content}
      ]
    response = client.chat.completions.create(
        model="default",
        messages=messages,
    )
    return(response.choices[0].message.content)