from data import *
from llm_wrapper import chat
import logging
import random
from typing import List

with open("personality-adjectives.txt", "r") as f:
    ADJECTIVES = [line.strip() for line in f.readlines() if line.strip()]

def generate_personality() -> str:
    return f"You are best described by and generally show the following personality traits in your threads and posts: {', '.join(random.choices(ADJECTIVES, k=15))}."

class Simulation:
    def __init__(self, forum: Forum):
        self._logger = logging.getLogger("forbot")
        self._time = 0
        self.model = "llama3"
        self.forum: Forum = forum
        self.users: List[User] = []
        self.threads: List[Thread] = []
        self.posts: List[Post] = []
    
    def generate_users(self, num_users: int):
        usernames = chat(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a creative AI that generates unique and interesting online usernames for forum users."},
                {"role": "user", "content": f"Generate {num_users + 5} unique and interesting online usernames for forum users interested in a forum with the name '{self.forum.name}', the purpose of '{self.forum.purpose}', and purported topic of '{self.forum.topic}'. Return the usernames as a comma-separated list. DO NOT INCLUDE ANYTHING ELSE IN YOUR RESPONSE. DO NOT USE AN INTRODUCTORY SENTENCE."}
            ]).message.content.strip().split(",")

        signatures = chat(
            model=self.model,
            messages=[
                {"role": "system", "content": "You are a creative AI that generates unique and interesting online signatures for forum users."},
                {"role": "user", "content": f"Generate {num_users + 5} unique and interesting online signatures for forum users interested in a forum with the name '{self.forum.name}', the purpose of '{self.forum.purpose}', and purported topic of '{self.forum.topic}'. Return the signatures as a comma-separated list. DO NOT INCLUDE ANYTHING ELSE IN YOUR RESPONSE. DO NOT USE AN INTRODUCTORY SENTENCE."}
            ]).message.content.strip().split(",")

        for i in range(num_users):
            username = usernames[i].strip()
            personality = generate_personality()
            signature = signatures[i].strip()
            forum_dedication = random.uniform(0.1, 1.0)
            active_start = random.randint(0, 20)
            active_end = active_start + random.randint(4, 8)
            active_hours = range(active_start, active_end % 24)

            user = User(
                id=len(self.users) + 1,
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
            self._logger.info(f"Simulated hour: {self._time % 24} (total time: {self._time} hours) - New threads: {len(new_threads)}, New posts: {len(new_posts)}")
    
    def simulate_user_activity(self, user: User, new_threads: List[Thread], new_posts: List[Post]) -> tuple[List[Thread], List[Post]]:
        if random.random() > user.forum_dedication:
            return [], []
        
        base_prompt = user.get_prompt(self.forum)

        added_threads = []
        added_posts = []

        for thread in new_threads:
            thread_posts = self.get_posts_in_thread(thread)
            own_posts = self.get_user_posts_in_thread(user, thread)

            engage = chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": base_prompt},
                    {"role": "user", "content": f"You have previously made {len(own_posts)} posts in the thread titled '{thread.title}'. There are currently {len(thread_posts)} posts in this thread. Decide whether you want to make another post in this thread based on your personality and forum dedication. Respond with 'YES' if you want to make a post, or 'NO' if you do not. DO NOT INCLUDE ANYTHING ELSE IN YOUR RESPONSE. DO NOT USE AN INTRODUCTORY SENTENCE."}
                ]).message.content.strip().upper()
            
            if "YES" not in engage:
                continue
                
            previous_posts = thread_posts[-30:] if len(thread_posts) >= 30 else thread_posts
            
            post_content = chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": base_prompt},
                    {"role": "system", "content": f"You are replying in the thread titled '{thread.title}'."},
                    {"role": "system", "content": f"Here are the previous posts in the thread in order from oldest to newest: {'\n'.join([f"{post.content}; written by {post.author.username}" for post in previous_posts])}"},
                    {"role": "user", "content": f"Generate the content to a post replying in the thread titled '{thread.title}'. Do not use the title as the first line of your post content. Make sure your post content is engaging and relevant to the forum topic. Use forum-like language and tone, such as lack of capitalization, grammar, and punctuation, as well as general internet acronyms and references, so long as they fit your stated personality. Make sure to direct your message towards other users in the thread. Avoid generating a long message. Be concise and to the point. DO NOT INCLUDE AN IRRELEVANT INTRODUCTORY SENTENCE."}
                ]).message.content.strip()
            
            post = Post(
                id=len(self.posts) + len(new_posts) + 1,
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

            title = chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": base_prompt},
                    {"role": "user", "content": f"{thread_focus} Generate a concise and catchy thread title for this new thread. DO NOT INCLUDE ANYTHING ELSE IN YOUR RESPONSE. DO NOT USE AN INTRODUCTORY SENTENCE."}
                ]).message.content.strip()

            post_content = chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": base_prompt},
                    {"role": "system", "content": f"You are creating a new thread titled '{title}'."},
                    {"role": "user", "content": f"{thread_focus} Generate the content to a post inside your new thread titled '{title}'. Keep in mind that you are making this thread and post for the following reason: {thread_focus} Make sure your post content is engaging and relevant to the forum topic. Use forum-like language and tone, such as lack of capitalization, grammar, and punctuation, as well as general internet acronyms and references, so long as they fit your stated personality. Avoid generating a long message. Be concise and to the point. DO NOT INCLUDE ANYTHING ELSE IN YOUR RESPONSE. DO NOT INCLUDE AN IRRELEVANT INTRODUCTORY SENTENCE."}
                ]).message.content.strip()

            thread = Thread(
                id=len(self.threads) + len(new_threads) + 1,
                title=title,
                author=user,
                category=None,
                created_date=self.forum.created_date.add_hours(self._time)
            )

            post = Post(
                id=len(self.posts) + len(new_posts) + 1,
                thread=thread,
                author=user,
                content=post_content + "\n\n" + user.signature,
                reply_to=[],
                created_date=self.forum.created_date.add_hours(self._time)
            )

            added_threads.append(thread)
            added_posts.append(post)
        
        return added_threads, added_posts