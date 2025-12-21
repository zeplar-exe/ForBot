from data import *
import logging
import random
from typing import List
import dspy
import random

BASE_TEXT_STYLE = "Use forum-like language and tone, such as lack of capitalization, grammar, and punctuation, as well as general internet acronyms and references, so long as they fit your stated personality. Make sure to direct your message towards other users in the thread. Avoid generating a long message. Be concise and to the point."

with open("personality-adjectives.txt", "r") as f:
    ADJECTIVES = [line.strip() for line in f.readlines() if line.strip()]

def generate_personality() -> str:
    return f"You are best described by and generally show the following personality traits in your threads and posts: {', '.join(random.choices(ADJECTIVES, k=15))}."

@dataclass
class UserPromptData:
    username: str
    personality: str

@dataclass
class PostPromptData:
    author: str
    thread_title: str

class SummarizeForumPrompt(dspy.Signature):
    forum_topic: str = dspy.InputField()
    forum_purpose: str = dspy.InputField()
    short_summary: str = dspy.OutputField()

class GenerateUsernamePrompt(dspy.Signature):
    topic: str = dspy.InputField()
    seed: int = dspy.InputField()
    username: str = dspy.OutputField()

class GenerateSignaturePrompt(dspy.Signature):
    topic: str = dspy.InputField()
    seed: int = dspy.InputField()
    user_signature: str = dspy.OutputField()

class ThreadEngagementPrompt(dspy.Signature):
    user: UserPromptData = dspy.InputField()
    forum_summary: str = dspy.InputField()
    thread_title: str = dspy.InputField()
    own_posts_count: int = dspy.InputField()
    total_posts_count: int = dspy.InputField()
    engage: bool = dspy.OutputField()

class CreateThreadPrompt(dspy.Signature):
    user: UserPromptData = dspy.InputField()
    forum_summary: str = dspy.InputField()
    style_instructions: str = dspy.InputField()
    thread_focus: str = dspy.InputField()
    thread_title: str = dspy.OutputField()
    thread_body: str = dspy.OutputField()

class CreatePostPrompt(dspy.Signature):
    user: UserPromptData = dspy.InputField()
    forum_summary: str = dspy.InputField()
    style_instructions: str = dspy.InputField()
    thread_title: str = dspy.InputField()
    previous_posts: list[PostPromptData] = dspy.InputField()
    post_content: str = dspy.OutputField()

class Simulation:
    def __init__(self, forum: Forum):
        self._logger = logging.getLogger("forbot")
        self._time = 0
        self.model = "llama3"
        self.forum: Forum = forum
        self.users: List[User] = []
        self.threads: List[Thread] = []
        self.posts: List[Post] = []

        self.generate_summaries()

    def generate_summaries(self):
        summarize_forum = dspy.Predict(SummarizeForumPrompt)
        summary = summarize_forum(
            instructions="Generate a short summary of the forum topic and purpose to be used in generating user personalities, threads, and posts. Aim for about 8-12 sentences of content while being concise and including information relevant to user discussion.",
            forum_topic=self.forum.topic,
            forum_purpose=self.forum.purpose
        ).short_summary
        self.forum_summary = summary
        self._logger.info(f"Generated forum summary: {summary}")
    
    def generate_users(self, num_users: int):
        generate_username = dspy.Predict(GenerateUsernamePrompt)
        generate_signature = dspy.Predict(GenerateSignaturePrompt)

        for i in range(num_users):
            username = generate_username(
                instructions="Generate a unique and interesting online username for a forum user given a topic for the forum. The seed influences stylistic variation only. Do not mention or encode it directly.",
                seed=random.randint(0, int(1e6)),
                topic=self.forum_summary,
            ).username.strip()
            personality = generate_personality()
            signature = generate_signature(
                instructions="Generate a unique and interesting online signature for a forum user given a topic for the forum. The seed influences stylistic variation only. Do not mention or encode it directly.",
                seed=random.randint(0, int(1e6)),
                topic=self.forum_summary,
            ).user_signature.strip()
            forum_dedication = random.uniform(0.1, 1.0)
            active_start = random.randint(0, 20)
            active_end = active_start + random.randint(4, 8)
            active_hours = range(active_start, active_end % 24)

            user = User(
                username=username,
                signature=signature,
                personality=personality,
                forum_dedication=forum_dedication,
                active_hours=active_hours
            )

            self.users.append(user)
            self._logger.info(f"Generated user: {user.username}")
    
    def get_user_threads(self, user: User) -> List[Thread]:
        return [thread for thread in self.threads if thread.author == user]
    
    def get_user_posts(self, user: User) -> List[Post]:
        return [post for post in self.posts if post.author == user]

    def get_user_posts_in_thread(self, user: User, thread: Thread) -> List[Post]:
        return [post for post in self.posts if post.author == user and post.thread == thread]

    def get_posts_in_thread(self, thread: Thread) -> List[Post]:
        return [post for post in self.posts if post.thread == thread]

    def advance_time(self, hours: int):
        new_threads = []
        new_posts = []

        for hour in range(hours):
            self._time += 1
            for user in self.users:
                if user.active_hours.start <= self._time % 24 < user.active_hours.stop:
                    added_threads, added_posts = self.simulate_user_activity(user, new_threads, new_posts)

                    new_threads.extend(added_threads)
                    self.threads.extend(added_threads)

                    new_posts.extend(added_posts)
                    self.posts.extend(added_posts)
            self._logger.info(f"Simulated hour: {self._time % 24} (total time: {self._time} hours) - New threads: {len(new_threads)}, New posts: {len(new_threads)}")
    
    def simulate_user_activity(self, user: User, new_threads: List[Thread], new_posts: List[Post]) -> tuple[List[Thread], List[Post]]:
        if random.random() > user.forum_dedication:
            return [], []

        added_threads = []
        added_posts = []

        for thread in new_threads:
            thread_posts = self.get_posts_in_thread(thread)
            own_posts = self.get_user_posts_in_thread(user, thread)

            engage = dspy.Predict(ThreadEngagementPrompt)

            if not engage(
                instructions="Decide whether the user would like to engage in the given thread based on their personality and previous participation.",
                user=UserPromptData(username=user.username, personality=user.personality),
                forum_summary=self.forum_summary,
                thread_title=thread.title,
                own_posts_count=len(own_posts),
                total_posts_count=len(thread_posts)
            ).engage:
                continue
                
            create_post = dspy.Predict(CreatePostPrompt)

            previous_posts = thread_posts[-30:] if len(thread_posts) >= 30 else thread_posts

            post_content = create_post(
                instructions="Create a concise and relevant forum post in response to the given thread title and previous posts, reflecting the user's personality and adhering to the specified style instructions.",
                user=UserPromptData(username=user.username, personality=user.personality),
                forum_summary=self.forum_summary,
                style_instructions=BASE_TEXT_STYLE,
                thread_title=thread.title,
                previous_posts=[PostPromptData(author=post.author.username, thread_title=post.thread.title) for post in previous_posts]
            ).post_content.strip()

            post = Post(
                thread=thread,
                author=user,
                content=post_content + "\n\n" + user.signature,
                reply_to=[],
                created_date=self.forum.created_date.add_hours(self._time)
            )

            added_posts.append(post)

        for post in new_posts:
            pass

        if random.random() < 0.35:
            foci = ["You decide to follow recent forum trends and hop on the bandwagon with a new post. If there are no significant recent trends, you decide to start your own.", 
                    "You decide to create a new thread to express your thoughts on a topic you care about.",
                    "You make a thread to share something interesting you found related to the forum topic."]
            thread_focus = random.choice(foci)

            create_thread = dspy.Predict(CreateThreadPrompt)
            
            thread_info = create_thread(
                instructions="Create a concise and catchy thread title and body for a new forum thread based on the user's personality and the specified focus for the thread.",
                user=UserPromptData(username=user.username, personality=user.personality),
                forum_summary=self.forum_summary,
                style_instructions=BASE_TEXT_STYLE,
                thread_focus=thread_focus
            )

            thread = Thread(
                title=thread_info.thread_title,
                author=user,
                category=None,
                created_date=self.forum.created_date.add_hours(self._time)
            )

            post = Post(
                thread=thread,
                author=user,
                content=thread_info.thread_body + "\n\n--------------------\n" + user.signature,
                reply_to=[],
                created_date=self.forum.created_date.add_hours(self._time)
            )

            added_threads.append(thread)
            added_posts.append(post)
        
        return added_threads, added_posts