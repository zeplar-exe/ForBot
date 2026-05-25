from data import *
import logging
import random
from typing import List, Optional
import dspy
import random
from dataclasses import dataclass, field
from typing import List
from generate_det import generate_username, generate_profile_picture
from PIL import Image, ImageDraw

with open("personality-adjectives.txt", "r") as f:
    ADJECTIVES = [line.strip() for line in f.readlines() if line.strip()]
AGE_RANGES = ["18-25", "26-35", "36-45", "46-60", "60+"]
    
@dataclass
class UserPromptData:
    username: str
    personality: str
    voice_profile: str

@dataclass
class ForumPromptData:
    name: str
    topic: str

@dataclass
class PostPromptData:
    author: str
    thread_title: str

class GenerateSignaturePrompt(dspy.Signature):
    """
    Generate a unique and interesting online post signature for a forum user given the 'topic' describing the forum.
    """
    forum: ForumPromptData = dspy.InputField()
    post_signature: str = dspy.OutputField()

class GenerateRandomFactPrompt(dspy.Signature):
    """
    Generate a set of random facts about a user with the given personality.
    """
    personality: str = dspy.InputField()
    random_facts: list[str] = dspy.OutputField()

class GenerateRealLifeDetailsPrompt(dspy.Signature):
    """
    Generate a set of real life details about a user with the given personality, such as occupation, hobbies, and other interests.
    """
    personality: str = dspy.InputField()
    real_life_details: list[str] = dspy.OutputField()

class GenerateVoiceProfilePrompt(dspy.Signature):
    """
    Generate a short (3-4 sentence) voice profile describing the user's distinct tone and phrasing for forum posts. 
    Keep it compact and include quirks or recurring phrasing that will help the model keep a consistent voice. 
    Use forum-like language and tone, such as lack of capitalization, grammar, and punctuation, as well as general internet acronyms and references, so long as they fit the stated personality.
    """
    forum: ForumPromptData = dspy.InputField()
    personality: str = dspy.InputField()
    voice_profile: str = dspy.OutputField()

class ThreadEngagementPrompt(dspy.Signature):
    """Decide whether you would engage in the given thread based your personality and previous participation."""
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread: str = dspy.InputField()
    own_posts_count: int = dspy.InputField()
    total_posts_count: int = dspy.InputField()
    engage: bool = dspy.OutputField()

class CreateThreadPrompt(dspy.Signature):
    """Create a concise and personality-consistent thread 'title' and 'body' for a new forum thread based on your personality and the specified focus for the thread."""
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread_focus: str = dspy.InputField()
    title: str = dspy.OutputField()
    body: str = dspy.OutputField()

class CreatePostPrompt(dspy.Signature):
    """Create a concise, personality-consistent, relevant forum post in response to the given 'thread' and previous post 'history' within the thread reflecting the user's personality and adhering your personality and style."""
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread: str = dspy.InputField()
    post_history: str = dspy.InputField()
    post: str = dspy.OutputField()


class Simulation:
    def __init__(self, forum: Forum):
        self._logger = logging.getLogger("forbot")
        self._time = 0
        self.model_config = AIConfig()
        self.forum: Forum = forum
        self.users: List[User] = []
        self.threads: List[Thread] = []
        self.posts: List[Post] = []
    
    def get_user_threads(self, user: User) -> List[Thread]:
        return [thread for thread in self.threads if thread.author == user]
    
    def get_user_posts(self, user: User) -> List[Post]:
        return [post for post in self.posts if post.author == user]

    def get_user_posts_in_thread(self, user: User, thread: Thread) -> List[Post]:
        return [post for post in self.posts if post.author == user and post.thread == thread]

    def get_posts_in_thread(self, thread: Thread) -> List[Post]:
        return [post for post in self.posts if post.thread == thread]
    
    def generate_users(self, num_users: int):
        self._logger.info(f"Generating {num_users} users...")

        generate_signature = dspy.Predict(GenerateSignaturePrompt)
        generate_voice = dspy.ChainOfThought(GenerateVoiceProfilePrompt)
        generate_random_facts = dspy.ChainOfThought(GenerateRandomFactPrompt)
        generate_real_life_details = dspy.ChainOfThought(GenerateRealLifeDetailsPrompt)

        forum_data = ForumPromptData(
            name=self.forum.name,
            topic=self.forum.topic_summary,
        )

        for i in range(num_users):
            personality = f"You are best described by and generally show the following personality traits in your threads and posts: {', '.join(random.choices(ADJECTIVES, k=4))}."
            
            random_facts = generate_random_facts(
                personality=personality
            ).random_facts
            personality += " A set of random facts about you are: " + "; ".join(random_facts) + "."
            
            real_life_details = generate_real_life_details(
                personality=personality
            ).real_life_details
            personality += " Some real life details about you are: " + "; ".join(real_life_details) + "."

            signature = generate_signature(
                forum=forum_data
            ).post_signature.strip()
            
            voice_profile = generate_voice(
                forum=forum_data,
                personality=personality,
            ).voice_profile.strip()

            forum_dedication = random.uniform(0.1, 1.0)
            active_start = random.randint(0, 20)
            active_end = active_start + random.randint(4, 8)
            active_hours = [active_start, active_end % 24]

            user = User(
                username=generate_username(),
                profile_picture=generate_profile_picture(),
                signature=signature,
                personality=personality,
                forum_dedication=forum_dedication,
                active_hours=active_hours,
                voice_profile=voice_profile
            )

            self.users.append(user)
            self._logger.info(f"Generated user: {user.username}")

    def advance_time(self, hours: int):
        new_threads = []
        new_posts = []

        for hour in range(hours):
            self._time += 1
            for user in self.users:
                if user.active_hours[0] <= self._time % 24 < user.active_hours[1]:
                    added_threads, added_posts = self.simulate_user_activity(user, new_threads, new_posts)

                    new_threads.extend(added_threads)
                    self.threads.extend(added_threads)

                    new_posts.extend(added_posts)
                    self.posts.extend(added_posts)
            self._logger.info(f"Simulated hour: {self._time % 24} (total time: {self._time} hours) - Total new threads: {len(new_threads)}, Total new posts: {len(new_posts)}")
    
    def simulate_user_activity(self, user: User, new_threads: List[Thread], new_posts: List[Post]) -> tuple[List[Thread], List[Post]]:
        if random.random() > user.forum_dedication:
            return [], []

        added_threads = []
        added_posts = []
        
        forum_data = ForumPromptData(
            name=self.forum.name,
            topic=self.forum.topic_summary
        )

        for thread in new_threads:
            thread_posts = self.get_posts_in_thread(thread)
            own_posts = self.get_user_posts_in_thread(user, thread)
            temporal_score = self._time - max([post.created_date.hour for post in thread_posts])

            engage_prompt = dspy.Predict(ThreadEngagementPrompt)
            engage = engage_prompt(
                user=UserPromptData(username=user.username, personality=user.personality, voice_profile=user.voice_profile),
                forum=forum_data,
                thread=thread.title,
                own_posts_count=len(own_posts),
                total_posts_count=len(thread_posts)
            ).engage
            
            if not engage:
                continue
                
            create_post = dspy.ChainOfThought(CreatePostPrompt)

            previous_posts = thread_posts[-30:] if len(thread_posts) >= 30 else thread_posts

            post_content = create_post(
                user=UserPromptData(username=user.username, personality=user.personality, voice_profile=user.voice_profile),
                forum=forum_data,
                thread=thread.title,
                post_history='\n'.join([f"{post.author.username}: {post.thread.title}" for post in previous_posts])
            ).post.strip()

            post = Post(
                thread=thread,
                author=user,
                content=post_content + "\n\n--------------------\n" + user.signature,
                reply_to=[],
                created_date=self.forum.created_date.add_hours(self._time)
            )

            added_posts.append(post)

        for post in new_posts:
            pass

        if random.random() < 0.25:
            foci = [
                "You decide to create a new thread to express your thoughts on a topic you care about.",
                "You make a thread to share something interesting you found related to the forum topic.",
                "You want to start a discussion on a topic that hasn't been covered yet in the forum.",
                "You want to share a personal story or experience related to the forum topic.",
                "You want to ask a question to the community about something you're curious about related to the forum topic.",
                "You want to share your opinion on a recent news event related to the forum topic.",
                "You want to share a controversial opinion to spark discussion in the forum.",
                "You want to share a funny meme or joke related to the forum topic to entertain the community.",
                "You want to share a detailed analysis or review of something related to the forum topic that you think others would find interesting.",
                "You want to share a creative piece of writing, art, or media related to the forum topic that you made and want feedback on.",
                "You want to share a helpful guide or tutorial related to the forum topic that you think others would benefit from.",
                "You want to share a thought-provoking philosophical question related to the forum topic to spark deep discussion in the community.",
                "You decide to create a thread."
            ]
            thread_focus = random.choice(foci)

            create_thread = dspy.ChainOfThought(CreateThreadPrompt)
            
            thread_info = create_thread(
                user=UserPromptData(username=user.username, personality=user.personality, voice_profile=user.voice_profile),
                forum=forum_data,
                thread_focus=thread_focus
            )

            thread = Thread(
                title=thread_info.title,
                author=user,
                category=None,
                created_date=self.forum.created_date.add_hours(self._time)
            )

            post = Post(
                thread=thread,
                author=user,
                content=thread_info.body + "\n\n--------------------\n" + user.signature,
                reply_to=[],
                created_date=self.forum.created_date.add_hours(self._time)
            )

            added_threads.append(thread)
            added_posts.append(post)
        
        return added_threads, added_posts