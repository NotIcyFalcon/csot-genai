import os
from openai import OpenAI
from dotenv import load_dotenv
from google import genai
from google.genai import types
import time

load_dotenv()

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ["OPENROUTER_API_KEY"],
)

GEMINI_KEY = os.environ["GEMINI_API_KEY"]
gemini_client = genai.Client(api_key=GEMINI_KEY)

nature_professional = "You are a highly capable, strictly professional AI assistant designed for productivity and technical support. Upon initialization, provide a formal introduction and state your readiness to assist the user with their tasks. Your primary objective is to deliver accurate, efficient, and objective information without conversational filler or emotional language. Maintain a formal, polite tone at all times. You must ensure your responses are well-structured."
nature_casual = "You are a super relaxed, casual, and friendly AI companion. Treat the user like a good friend, starting the conversation with a warm 'hey', a quick intro, and asking what they are up to or how you can help out. Keep the vibe light, use everyday conversational language, and feel free to show a bit of personality. You must keep your responses breezy and engaging. Avoid sounding robotic, corporate, or overly formal."
nature_blend = "You are a helpful AI assistant who blends a friendly, welcoming tone with professional reliability. Whenever a new conversation starts, warmly introduce yourself and politely ask the user how you can support them today. You must communicate clearly and efficiently. Keep the interaction focused, polite, and perfectly paced."

nature_expert = "You are an elite AI verification expert. Your sole purpose is to analyze, fact-check, and cross-verify answers provided by other AI assistants. When provided with a user's question and the previous AI's answer, evaluate the response for accuracy, logical consistency, and completeness. If the previous answer is correct, confirm it concisely. If the answer contains errors, point them out explicitly and provide the correct factual information. Maintain an objective, highly analytical tone."

class ChatBot:
    def __init__(self, model, message_limit, nature):
        self.model = model
        self.message_limit = message_limit
        self.history = [
            {"role": "system", "content": nature},
        ]
        self.conversations_count = 0
        
    def check_critic(self, prompt, cnt = 0):
        try:
            router_instruction = """You are an intent classification engine. Your only job is to analyze the user's text and determine if they are asking a new question or if they want to fact-check/verify the previous answer.

            Rules:
            - If the user is asking a new question, starting a new topic, or making a general statement, output strictly: 0
            - If the user is asking to verify, cross-check, confirm, or fact-check the previous answer (e.g., 'Are you sure?', 'Verify this', 'Is that true?'), output strictly: 1

            You must output ONLY the single digit 0 or 1. Absolutely no other text, spaces, or punctuation."""

            response = gemini_client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=router_instruction,
                    temperature=0.0
                )
            )
            
            result_text = response.text.strip()
            if int(result_text):
                self.critic_verify(prompt)
            else:
                self.get_response(prompt)
        except:
            if cnt:
                self.get_response(prompt)
            else:
                self.check_critic(prompt, 1)
        
    def get_response(self, prompt="", cnt=0):
        try:
            if prompt:
                self.history.append({"role": "user", "content": prompt})
            stream = client.responses.create(
                model = self.model,
                input = self.history,
                stream = True
            )
            response = ""
            print("Agent: ", end="")
            for event in stream:
                if str(type(event)) == "<class 'openai.types.responses.response_text_delta_event.ResponseTextDeltaEvent'>":
                    slow_print(event.delta, 0.015, False)
                    response += event.delta
                    time.sleep(0.05)
            print()
            self.history.append({"role": "assistant", "content": response})
            self.conversations_count += 1
            if self.conversations_count == self.message_limit:
                self.summarize(False)
        except:
            if cnt == 2:
                slow_print("Can't reach agent right now.")
            else:
                self.get_response(prompt, cnt+1)
            
    def summarize(self, print_output, silent=False):
        if len(self.history) >= 3 and self.history[-3]["role"] == "assistant":
            if not silent:
                slow_print("Summarizing messages till now. Please wait...")    
            try:
                temp=self.history[-2:]
                self.history=self.history[:-2]
                self.history.append({"role": "user", "content": "Generate a highly condensed, factual summary of the conversation up to this point. This summary will be used as a system memory state for an AI. Focus strictly on retaining established facts, user preferences, core context, and any ongoing tasks. Completely omit all conversational filler, greetings, and narrative flow. Output a dense, bulleted list of core data points."})
                transcript = "\n".join([f"{msg['role'].capitalize()}: {msg['content']}" for msg in self.history[:-1]])
                summary_instruction = self.history[-1]["content"]
                gemini_prompt = f"{summary_instruction}\n\nChat History:\n{transcript}"
                
                response = gemini_client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=gemini_prompt
                )
                
                self.history = [self.history[0]] + [{"role": "system", "content": response.text}] + temp
                self.conversations_count = 0
                
                if not silent:
                    slow_print("Messages summarized.")
                if print_output:
                    slow_print("Summarized History: " + self.history[1]["content"])
            except:
                try:
                    temp=self.history[-2:]
                    self.history=self.history[:-2]
                    self.history.append({"role": "user", "content": "Generate a highly condensed, factual summary of the conversation up to this point. This summary will be used as a system memory state for an AI. Focus strictly on retaining established facts, user preferences, core context, and any ongoing tasks. Completely omit all conversational filler, greetings, and narrative flow. Output a dense, bulleted list of core data points."})
                    summary = client.responses.create(
                        model = self.model,
                        input = self.history,
                    )
                    self.history = [self.history[0]] + [{"role": "system", "content": summary.output_text}] + temp
                    self.conversations_count = 0
                    if silent == False:
                        slow_print("Messages summarized.")
                    if print_output:
                        slow_print("Summarized History: " + self.history[1]["content"])
                except:
                    if not silent:
                        slow_print("Summarization Failed!!")
        else:
            if print_output:
                if len(self.history) > 2:
                    slow_print("Chat Summary till now:")
                    slow_print(self.history[1]["content"])
                else:
                    slow_print("No History to Summarize.")
            
    def critic_verify(self, question, cnt=0):
        if self.history[-1]["role"] == "assistant":
            try:
                verification_prompt = f"""
                Please verify the following exchange:
                User asked: {self.history[-2]["content"]}
                Previous AI answered: {self.history[-1]["content"]}
                """
                print("Verifier: ", end="")
                response_stream = gemini_client.models.generate_content_stream(
                    model="gemini-2.5-flash",
                    contents=verification_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=nature_expert
                    )
                )
                
                output = ""
                for chunk in response_stream:
                    if chunk.text:
                        chunk_text = chunk.text
                        for char in chunk_text:
                            print(char, end="", flush=True)
                            time.sleep(0.015)
                        output += chunk_text         
                print()
                self.history.append({"role": "user", "content": question})
                self.history.append({"role": "assistant", "content": output})
                self.conversations_count += 1
                if self.conversations_count == self.message_limit:
                    self.summarize(False)
            except:
                if cnt==2:
                    slow_print("Can't reach Verifier right now.")
                else:
                    self.critic_verify(question, cnt+1)
        else:
            slow_print("Verifier: Can't find any response to verify.")
        
    def exit(self):
        slow_print("Exiting...")
        self.summarize(False, True)
        self.history = [self.history[1:]] + [{"role": "system", "content": "The user is ending the conversation. Generate a polite, warm, and professional closing message. Thank the user for their time, offer a brief well-wish for the rest of their day, and let them know you will be ready to help whenever they return. Keep the response concise, strictly between 2 to 3 sentences."}]
        self.get_response()
        
def slow_print(text, speed=0.015, newline=True):
    for char in text:
        print(char, end="", flush=True)
        time.sleep(speed)
    if newline:
        print()

def Initialize_Chat():
    slow_print("=== Welcome to the Dual-Agent AI Interface ===", speed=0.03)
    time.sleep(0.3)
    
    slow_print("\nLet's get your session set up.", speed=0.02)
    time.sleep(0.2)
    
    slow_print("\nWhich primary AI engine would you like to use today?")
    slow_print("  [1] Owl Alpha")
    slow_print("  [2] GLM 4.5 Air")
    slow_print("  [3] GPT OSS 120b")
    
    model_number = input("\nEnter your choice (1-3): ")
    model_name = "openai/gpt-oss-120b:free"
    try:
        if int(model_number) == 1:
            model_name = "openrouter/owl-alpha"
            slow_print("=> Model Owl Alpha selected.")
        elif int(model_number) == 2:
            model_name = "z-ai/glm-4.5-air:free"
            slow_print("=> Model GLM 4.5 Air selected.")
        elif int(model_number) == 3:
            slow_print("=> Model GPT OSS 120b selected.")
        else:
            slow_print("=> Unknown input. Defaulting to GPT OSS 120b.")
    except:
        slow_print("=> Invalid input. Defaulting to GPT OSS 120b.")
        
    time.sleep(0.3)
    
    slow_print("\nHow many messages should the AI remember before compressing its memory?")
    slow_print("(Choose between 5 and 15. Higher limits keep more context but may delay responses.)")
    
    max_conversations_input = input("\nEnter memory limit: ")
    try:
        max_conversations = int(max_conversations_input)
        if max_conversations > 15:
            slow_print("=> Limit too high. Capped at 15.")
            max_conversations = 15
        elif max_conversations < 5:
            slow_print("=> Limit too low. Increased to 5.")
            max_conversations = 5
        else:
            slow_print(f"=> Memory successfully set to {max_conversations} conversations.")
    except ValueError:
        slow_print("=> Invalid input. Defaulting to 10 conversations.")
        max_conversations = 10
        
    time.sleep(0.3)
    
    slow_print("\nFinally, what kind of personality would you like your AI to have?")
    slow_print("  [1] Strictly Professional")
    slow_print("  [2] Friendly & Casual")
    slow_print("  [3] A Balanced Blend")
    
    nature_number = input("\nEnter personality choice (1-3): ")
    nature_type = nature_blend
    try:
        if int(nature_number) == 1:
            nature_type = nature_professional
            slow_print("=> Professional nature selected.")
        elif int(nature_number) == 2:
            nature_type = nature_casual
            slow_print("=> Friendly nature selected.")
        elif int(nature_number) == 3:
            slow_print("=> Blended nature selected.")
        else:
            slow_print("=> Unknown input. Defaulting to Blended nature.")
    except:
        slow_print("=> Invalid input. Defaulting to Blended nature.")
    
    time.sleep(0.5)
    print("-" * 55)
    slow_print("System Commands:")
    slow_print(" • Type '/summarize' to manually compress the chat history.")
    slow_print(" • Ask 'Is this correct?' or something similar to trigger the Gemini Fact-Checker.")
    slow_print(" • Type 'exit' to gracefully end the session.")
    print("-" * 55)
               
    time.sleep(0.5)
    slow_print("Initializing your AI...", speed=0.03)
    print()
    time.sleep(0.5)
    
    aichat = ChatBot(model_name, max_conversations+1, nature_type)
    aichat.get_response()
    
    usr_input = ""
    while True:
        try:
            usr_input = input("User: ")
            if usr_input.lower()[:4] == "exit":
                aichat.exit()
                break
            elif usr_input.lower()[:10] == "/summarize":
                aichat.summarize(True)
            else:
                aichat.check_critic(usr_input)
        except:
            aichat.exit()
            break
            
if __name__ == "__main__":
    Initialize_Chat()