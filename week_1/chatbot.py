import os
import time
from dotenv import load_dotenv
from openai import OpenAI
from google import genai
from google.genai import types

load_dotenv()

openrouter_api = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

gemini_api = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

bot_personality = "You are a smart and friendly AI. Help the user clearly and accurately. Start the conversation with a nice greeting and introduce yourself. Don't be too stiff or too casual."

summary_instruction = "Make a short, bulleted list of the main facts, context, and tasks from this chat. Leave out the greetings and normal talk. Just keep the important memory points."

goodbye_message = "The user wants to leave. Say a quick, polite goodbye in 2 sentences or less."

verifier_personality = "You are a strict fact-checker. Look at the user's original question and the AI's answer. Tell the user if the AI was right or wrong. Fix any mistakes clearly and get straight to the point."

chat_memory = []
message_count = 0
chat_limit = 8
chosen_model = ""

def check_intent(text_input, try_again=False):
    router_rules = """Read the user's message.
If the user is asking to double-check, verify, confirm, fact-check, or asking if the AI's last answer was correct (like "Are you sure?", "Is that accurate?", "Verify this"), you must output the number 1.
If the user is asking a brand new question, changing the subject, or just talking normally, output the number 0.
Output ONLY the digit 0 or 1. No other words or punctuation."""

    try:
        result = gemini_api.models.generate_content(
            model="gemini-2.5-flash",
            contents=text_input,
            config=types.GenerateContentConfig(
                system_instruction=router_rules,
                temperature=0.0
            )
        )
        answer = result.text.strip()
        if answer == "1":
            return 1
        else:
            return 0
    except Exception:
        if try_again == False:
            return check_intent(text_input, True)
        return 0

def make_summary(show_text, quiet=False):
    global chat_memory
    global message_count
    
    if quiet == False:
        print("\nCompressing chat history...")
        
    chat_memory.append({"role": "user", "content": summary_instruction})
    
    chat_text = ""
    for msg in chat_memory[:-1]:
        chat_text += msg['role'] + ": " + msg['content'] + "\n"
        
    prompt_for_gemini = chat_memory[-1]["content"] + "\n\nChat History:\n" + chat_text
    
    response = gemini_api.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt_for_gemini
    )
    
    chat_memory = [chat_memory[0]]
    chat_memory.append({"role": "system", "content": response.text})
    message_count = 0
    
    if quiet == False:
        print("History compressed.")
    if show_text == True:
        print("\nSaved Memory:\n" + chat_memory[1]["content"] + "\n")

def get_ai_reply(user_text=""):
    global message_count
    
    if user_text != "":
        chat_memory.append({"role": "user", "content": user_text})
        
    stream = openrouter_api.responses.create(
        model=chosen_model,
        input=chat_memory,
        stream=True
    )
    
    full_reply = ""
    print("Bot: ", end="")
    
    for piece in stream:
        if str(type(piece)) == "<class 'openai.types.responses.response_text_delta_event.ResponseTextDeltaEvent'>":
            text_chunk = piece.delta
            print(text_chunk, end="", flush=True)
            full_reply += text_chunk
            time.sleep(0.05)
    print()
    
    chat_memory.append({"role": "assistant", "content": full_reply})
    message_count += 1
    
    if message_count >= chat_limit:
        make_summary(False)

def verify_last_message(user_text):
    global message_count
    
    if len(chat_memory) >= 2 and chat_memory[-1]["role"] == "assistant":
        original_question = chat_memory[-2]["content"]
        ai_answer = chat_memory[-1]["content"]
        
        check_prompt = "User asked: " + original_question + "\nPrevious AI answered: " + ai_answer
        
        print("Checker: ", end="")
        
        stream_response = gemini_api.models.generate_content_stream(
            model="gemini-2.5-flash",
            contents=check_prompt,
            config=types.GenerateContentConfig(
                system_instruction=verifier_personality
            )
        )
        
        checker_reply = ""
        for chunk in stream_response:
            if chunk.text:
                chunk_text = chunk.text
                for char in chunk_text:
                    print(char, end="", flush=True)
                    time.sleep(0.015)
                checker_reply += chunk_text         
        print()
        
        chat_memory.append({"role": "user", "content": user_text})
        chat_memory.append({"role": "assistant", "content": checker_reply})
        message_count += 1
        
        if message_count >= chat_limit:
            make_summary(False)
    else:
        print("Checker: Can't find any response to verify right now.")

def quit_chat():
    chat_memory.append({"role": "system", "content": goodbye_message})
    get_ai_reply()

def start_bot():
    global chosen_model
    global chat_memory
    
    print("Which bot do you want?")
    print("1 for Owl Alpha")
    print("2 for GPT OSS 120b")
    
    user_choice = input("Enter 1 or 2: ")
    
    chosen_model = "openai/gpt-oss-120b:free"
    if user_choice == "1":
        chosen_model = "openrouter/owl-alpha"
        
    chat_memory.append({"role": "system", "content": bot_personality})
    
    get_ai_reply()
    
    print("\nCommands:")
    print("Type /compress to summarize history")
    print("Type exit or quit to stop")
    print("Ask if the last answer was correct to trigger the fact-checker\n")
    
    while True:
        try:
            my_input = input("You: ")
        except (KeyboardInterrupt, EOFError):
            quit_chat()
            break
            
        if my_input.strip() == "":
            continue
            
        cmd = my_input.lower().strip()
        
        if cmd == "exit" or cmd == "quit":
            quit_chat()
            break
        elif cmd == "/compress":
            make_summary(True)
        else:
            is_checking = check_intent(my_input)
            
            if is_checking == 1:
                verify_last_message(my_input)
            else:
                get_ai_reply(my_input)

if __name__ == "__main__":
    start_bot()