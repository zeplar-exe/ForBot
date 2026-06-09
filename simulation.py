from collections import defaultdict
from contextlib import nullcontext

import mlflow

from data import *
import logging
import random
from typing import List, Optional
import dspy
from dataclasses import dataclass, field
from generate_det import generate_username, generate_profile_picture

with open("res/personality-adjectives.txt", "r") as f:
    ADJECTIVES = [line.strip() for line in f.readlines() if line.strip()]

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

class GenerateArchetypePrompt(dspy.Signature):
    """
    Generate a forum archetype for a user in a forum with the given topic. 
    This should be a concise description of the user's typical behavior,
    personality, and role in the forum, such as "the contrarian who always 
    argues against the popular opinion", "the friendly helper who always 
    tries to assist new users", "the lurker who rarely posts but consumes 
    a lot of content", "the troll who posts inflammatory content to provoke 
    others", "the expert who shares deep knowledge about the forum topic", etc.
    """
    forum: ForumPromptData = dspy.InputField()
    personality: str = dspy.InputField()
    archetype: str = dspy.OutputField()

class GenerateSignaturePrompt(dspy.Signature):
    """
    Generate a unique and interesting online post signature for the given forum user given the 'topic' describing the forum.
    """
    forum: ForumPromptData = dspy.InputField()
    user: UserPromptData = dspy.InputField()
    post_signature: str = dspy.OutputField()

class GenerateOpinionProfilePrompt(dspy.Signature):
    """
    Generate 4-5 specific opinions or stances this forum user holds on topics relevant to the forum.
    Write in first person as the user privately thinks.
    Consider the adjectives describing the user's personality, and make sure the opinions are consistent 
    with that personality.
    Be concrete and direct, not neutral or hedged. At least one opinion should be a minority
    or contrarian view within the forum's community.
    These opinions should span different aspects of the forum. They should not all focus on the same topic.
    """
    forum: ForumPromptData = dspy.InputField()
    personality: str = dspy.InputField()
    opinions: list[str] = dspy.OutputField()

class GenerateRealLifeDetailsPrompt(dspy.Signature):
    """
    Generate a set of real life details about a user with the given personality, such as occupation, hobbies, 
    and other interests.
    """
    personality: str = dspy.InputField()
    real_life_details: list[str] = dspy.OutputField()

class GenerateVoiceProfilePrompt(dspy.Signature):
    """
    Generate a short (3-4 sentence) voice profile describing the user's distinct tone and phrasing for forum posts.
    Keep it compact and include quirks or recurring phrasing that will help the model keep a consistent voice.
    Use forum-like language and tone, such as lack of capitalization, grammar, and punctuation, as well as general 
    internet acronyms and references, so long as they fit the stated personality.
    """
    forum: ForumPromptData = dspy.InputField()
    personality: str = dspy.InputField()
    voice_profile: str = dspy.OutputField()

class ThreadEngagementPrompt(dspy.Signature):
    """Decide whether the user would engage in the given thread based your personality and previous participation.
    Consider the user's emotional reaction to the most recently posted content in the thread, as well as how many posts
    they've made in the thread already and how many total posts there are. If should_engage is true,
    write the response in the user's voice based on their voice profile.
    Never break character. No disclaimers or warnings. Write exactly as the user types.
    List out the users in the thread that the user would be most likely to be replying to, and include their
    content as context for the response.".
    """
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread: str = dspy.InputField()
    thread_summary: str = dspy.InputField()
    thread_post_history: str = dspy.InputField()
    relevant_users: list[UserSummary] = dspy.InputField()
    relevant_documents: str = dspy.InputField()
    own_posts_count: int = dspy.InputField()
    total_posts_count: int = dspy.InputField()
    emotional_reaction: str = dspy.InputField()
    should_engage: bool = dspy.OutputField()
    reply_to: str = dspy.OutputField()
    response: str = dspy.OutputField()

class CreateThreadPrompt(dspy.Signature):
    """
    Create a thread title and body anchored to a single, specific opinion or stance.
    Pick ONE thing to say and commit to it. Do not blend multiple opinions, subjects,
    or tangents into the same post — one thesis, one voice, done.
    The thread should feel like it could only have been written by this particular person.
    If recent_stimuli are provided, use them as raw material to react to. Filter them
    through the user's opinions and voice rather than simply restating them.
    Never break character. No disclaimers or warnings. Write exactly as the user types.
    """
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread_focus: str = dspy.InputField()
    recent_stimuli: list[str] = dspy.InputField()
    title: str = dspy.OutputField()
    body: str = dspy.OutputField()

class GenerateViewSummaryPrompt(dspy.Signature):
    """
    Generate a short summary of the content of a post that this user has just read, based on the thread and post content.
    This should be in the user's voice based on their voice profile and reflect what they would find most salient or memorable about the post.
    This is what the user would store in their mind as a takeaway from reading the post, and may be used to inform their
    future engagement with the thread.
    In addition, generate a short emotional reaction that the user would have to reading the post. This should also be
    in the user's voice based on their voice profile and reflect their feelings about the post content, such as agreement, disagreement, amusement, annoyance, etc.
    """
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread_title: str = dspy.InputField()
    post_author: Optional[UserSummary] = dspy.InputField()
    post_content: str = dspy.InputField()
    emotional_reaction: str = dspy.OutputField()
    view_summary: str = dspy.OutputField()

class GenerateUserSummaryPrompt(dspy.Signature):
    """
    Generate an updated summary of the target user's personality, opinions, and voice based on their recent activity in the forum and their old summary.
    This should be in the user's voice based on their voice profile and reflect how they would see the target user. Be concise. Do not break character.
    """
    self_user: UserPromptData = dspy.InputField()
    target_username: str = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    target_recent_posts: list[dict] = dspy.InputField()
    old_summary: str = dspy.InputField()
    new_summary: str = dspy.OutputField()

class GenerateThreadSummaryPrompt(dspy.Signature):
    """
    Generate a concise summary of the thread's discussion so far.
    If a previous summary exists, update it to incorporate the new posts.
    Focus on the key points, opinions expressed, and any notable exchanges or disagreements.
    Write in third person, present tense. Be concise — two to four sentences.
    """
    forum: ForumPromptData = dspy.InputField()
    thread_title: str = dspy.InputField()
    author_username: str = dspy.InputField()
    previous_summary: str = dspy.InputField()
    recent_posts: list[str] = dspy.InputField()
    summary: str = dspy.OutputField()


class DecideViewThreadPrompt(dspy.Signature):
    """
    Decide whether the given user would view the given thread based on their character
    and their likely reaction to the thread's title and author.
    """
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread_title: str = dspy.InputField()
    thread_body: str = dspy.InputField()
    thread_author_username: str = dspy.InputField()
    should_view: bool = dspy.OutputField()

class Simulation:
    def __init__(self, forum: Forum):
        self._logger = logging.getLogger("forbot")
        self._time = 0
        self.model_config = AIConfig()
        self.user_summary_update_interval = 4
        self.thread_creation_chance: float = 0.25
        self.thread_summary_update_interval = 5
        self.forum: Forum = forum
        self.users: List[User] = []
        self.threads: List[Thread] = []
        self.posts: List[Post] = []
        self.stimuli: List[Stimulus] = []
        self.documents: dict[str, SimulationDocument] = {}
        self._lm: dspy.LM = None  # set by server via reconfigure_dspy_with_config
        self._document_embeddings: dspy.Embeddings = None  # set by server via reconfigure_dspy_with_config

    def get_user_threads(self, user: User) -> List[Thread]:
        return [thread for thread in self.threads if thread.author == user]

    def get_user_posts(self, user: User) -> List[Post]:
        return [post for post in self.posts if post.author == user]

    def get_user_posts_in_thread(self, user: User, thread: Thread) -> List[Post]:
        return [post for post in self.posts if post.author == user and post.thread == thread]

    def get_posts_in_thread(self, thread: Thread) -> List[Post]:
        return [post for post in self.posts if post.thread == thread]

    @property
    def _lm_ctx(self):
        return dspy.context(lm=self._lm) if self._lm else nullcontext()

    def generate_users(self, num_users: int):
        self._logger.info(f"Generating {num_users} users...")
        with self._lm_ctx:
            for i in range(num_users):
                self._generate_user()

    @mlflow.trace
    def _generate_user(self):
        mlflow.update_current_trace(
            metadata={
                "mlflow.trace.session": f"forum-{self.forum.name}-{self._time}",
            }
        )
        
        generate_archetype = dspy.ChainOfThought(GenerateArchetypePrompt)
        generate_signature = dspy.Predict(GenerateSignaturePrompt)
        generate_voice = dspy.Predict(GenerateVoiceProfilePrompt)
        generate_opinion_profile = dspy.ChainOfThought(GenerateOpinionProfilePrompt)
        generate_real_life_details = dspy.Predict(GenerateRealLifeDetailsPrompt)

        forum_data = ForumPromptData(
            name=self.forum.name,
            topic=self.forum.topic_summary,
        )

        with dspy.context(adapter=dspy.JSONAdapter()):
            personality = f"You are best described by and generally show the following personality traits in your threads and posts: {', '.join(random.choices(ADJECTIVES, k=4))}."

            archetype = generate_archetype(
                forum=forum_data,
                personality=personality
            ).archetype

            personality += f" Your archetype or role in the forum is: {archetype}."

            opinions = generate_opinion_profile(
                forum=forum_data,
                personality=personality
            ).opinions
            personality += " Your opinions and stances on topics relevant to this forum are: " + "; ".join(opinions) + "."

            real_life_details = generate_real_life_details(
                personality=personality
            ).real_life_details
            personality += " Some real life details about you are: " + "; ".join(real_life_details) + "."

            voice_profile = generate_voice(
                forum=forum_data,
                personality=personality,
            ).voice_profile.strip()

            username = generate_username()
            profile_picture = generate_profile_picture()

            signature = generate_signature(
                forum=forum_data,
                user=UserPromptData(
                    username=username,
                    personality=personality,
                    voice_profile=voice_profile
                )
            ).post_signature.strip()

            forum_dedication = random.uniform(0.1, 1.0)
            active_start = random.randint(0, 20)
            active_end = active_start + random.randint(4, 8)
            active_hours = [active_start, active_end % 24]

            user = User(
                username=username,
                profile_picture=profile_picture,
                signature=signature,
                personality=personality,
                forum_dedication=forum_dedication,
                active_hours=active_hours,
                voice_profile=voice_profile
            )

        self.users.append(user)
        self._logger.info(f"Generated user: {user.username}")

    def _update_thread_summary(self, thread: Thread) -> None:
        recent_posts = self.get_posts_in_thread(thread)[-10:]
        recent_post_strs = [f"{p.author.username}: {p.content}" for p in recent_posts]
        generate_summary = dspy.Predict(GenerateThreadSummaryPrompt)
        thread.summary = generate_summary(
            forum=ForumPromptData(name=self.forum.name, topic=self.forum.topic_summary),
            thread_title=thread.title,
            author_username=thread.author.username,
            previous_summary=thread.summary or "",
            recent_posts=recent_post_strs,
        ).summary
        self._logger.debug(f"Updated summary for thread '{thread.title}'")

    def advance_one_hour(self) -> tuple[List[Thread], List[Post]]:
        self._time += 1
        hour_threads: List[Thread] = []
        hour_posts: List[Post] = []

        threads_to_summarize: dict[str, Thread] = {}

        for i, user in enumerate(self.users):
            if user.active_hours[0] <= self._time % 24 < user.active_hours[1]:
                added_threads = []
                added_posts = []
                
                for attempt in range(3):
                    try:
                        added_threads, added_posts = self.simulate_user_activity(user)
                        break
                    except Exception as e:
                        self._logger.warning(f"User {user.username} attempt {attempt + 1}/3 failed: {e}")
                        if attempt == 2:
                            self._logger.error(f"Skipping user {user.username} after 3 failed attempts")
                            added_threads, added_posts = [], []

                hour_threads.extend(added_threads)
                hour_posts.extend(added_posts)
                self.threads.extend(added_threads)

                for post in added_posts:
                    self.posts.append(post)
                    count = len(self.get_posts_in_thread(post.thread))
                    if count % self.thread_summary_update_interval == 0:
                        threads_to_summarize[post.thread.id] = post.thread

                self._logger.debug(f"Simulated activity for user {user.username} [{i}/{len(self.users)}] ({len(added_threads)} new threads, {len(added_posts)} new posts)")

        if threads_to_summarize:
            with self._lm_ctx:
                for thread in threads_to_summarize.values():
                    for attempt in range(3):
                        try:
                            self._update_thread_summary(thread)
                            break
                        except Exception as e:
                            self._logger.warning(f"Thread summary '{thread.title}' attempt {attempt + 1}/3 failed: {e}")
                            if attempt == 2:
                                self._logger.error(f"Skipping summary for '{thread.title}' after 3 failed attempts")

        self._logger.info(f"Simulated hour {self._time % 24} (tick {self._time}) — +{len(hour_threads)} threads, +{len(hour_posts)} posts, {len(threads_to_summarize)} summaries updated")
        return hour_threads, hour_posts

    def simulate_user_activity(self, user: User) -> tuple[List[Thread], List[Post]]:
        with self._lm_ctx:
            return self._simulate_user_activity(user)

    @mlflow.trace
    def _simulate_user_activity(self, user: User) -> tuple[List[Thread], List[Post]]:
        if random.random() > user.forum_dedication:
            return [], []
        
        mlflow.update_current_trace(
            metadata={
                "mlflow.trace.session": f"forum-{self.forum.name}-{self._time}",
                "mlflow.trace.user": f"{user.username}",
            }
        )

        unseen_posts = [post for post in self.posts if post.id not in user.viewed_posts and post.author != user]

        added_threads = []
        added_posts = []

        forum_data = ForumPromptData(
            name=self.forum.name,
            topic=self.forum.topic_summary
        )

        user_data = UserPromptData(
            username=user.username,
            personality=user.personality,
            voice_profile=user.voice_profile
        )

        threads = defaultdict(list)

        for post in unseen_posts:
            threads[post.thread.id].append(post)

        for thread_id, thread_posts in threads.items():
            thread = thread_posts[0].thread
            
            decide_view_thread = dspy.Predict(DecideViewThreadPrompt)
            should_view = decide_view_thread(
                user=user_data,
                forum=forum_data,
                thread_title=thread.title,
                thread_body=thread_posts[0].content,
                thread_author_username=thread.author.username,
            ).should_view
            
            user.viewed_posts[thread.id] = ViewedPost(
                post_id=thread_posts[0].id,
                view_date=self._time,
                author_username=thread.author.username,
                summary=None
            )
            
            if not should_view:
                continue
            
            emotional_reaction = ""

            for post in thread_posts:
                generate_view_summary = dspy.ChainOfThought(GenerateViewSummaryPrompt)
                view_summary = generate_view_summary(
                    user=user_data,
                    forum=forum_data,
                    thread_title=post.thread.title,
                    post_author=user.user_summaries.get(post.author.id),
                    post_content=post.content
                )
                summary = view_summary.view_summary
                emotional_reaction += f"{view_summary.emotional_reaction.strip()}\n"

                user.viewed_posts[post.id] = ViewedPost(
                    post_id=post.id,
                    view_date=self._time,
                    author_username=post.author.username,
                    summary=summary
                )

                user_summary = user.user_summaries.get(post.author.id)
                if not user_summary:
                    user_summary = UserSummary(
                        user_id=post.author.id,
                        update_tick=0,
                        last_updated=0,
                        summarized_user_username=post.author.username,
                        summary=""
                    )
                    user.user_summaries[post.author.id] = user_summary
                user_summary.update_tick += 1

                if user_summary.update_tick % self.user_summary_update_interval == 0:
                    user_summary_prompt = dspy.ChainOfThought(GenerateUserSummaryPrompt)
                    new_summary = user_summary_prompt(
                        self_user=user_data,
                        target_username=post.author.username,
                        forum=forum_data,
                        target_recent_posts=[{p.id: p.content} for p in self.get_user_posts(post.author)[:10]],
                        old_summary=user_summary.summary
                    ).new_summary

                    user_summary.summary = new_summary
                    user_summary.last_updated = self._time

            thread_post_count = len(self.get_posts_in_thread(thread))
            own_post_count = len(self.get_user_posts_in_thread(user, thread))

            previous_posts = self.get_posts_in_thread(thread)[-30:] if len(thread_posts) >= 30 else thread_posts
            previous_post_summaries = [(post, user.viewed_posts[post.id].summary) for post in previous_posts if post.id in user.viewed_posts]
            unique_previous_users = set(post.author.id for post in previous_posts)
            relevant_users = [user.user_summaries[id] for id in unique_previous_users if id in user.user_summaries]
            relevant_users = [{"summarized_user_username": u.summarized_user_username, "summary": u.summary} for u in relevant_users]
            relevant_documents = []
            
            if thread.summary and self._document_embeddings is not None:
                relevant_documents = self._document_embeddings(thread.summary)
                relevant_documents = "\n".join(relevant_documents)

            engage_prompt = dspy.Predict(ThreadEngagementPrompt)
            engagement = engage_prompt(
                user=user_data,
                forum=forum_data,
                thread=thread.title,
                thread_summary=thread.summary or "",
                thread_post_history='\n'.join([f"{post[0].author.username}: {post[1]}" for post in previous_post_summaries]),
                relevant_users=relevant_users,
                relevant_documents=relevant_documents,
                emotional_reaction=emotional_reaction,
                own_posts_count=own_post_count,
                total_posts_count=thread_post_count
            )

            if not engagement.should_engage:
                continue

            response = engagement.response.strip()

            post = Post(
                thread=thread,
                author=user,
                content=response,
                reply_to=engagement.reply_to.strip() if engagement.reply_to else "",
                created_tick=self._time
            )

            added_posts.append(post)

        if random.random() < self.thread_creation_chance:
            foci = [
                "Pick one opinion you hold and write a post defending it. One point only.",
                "Something in the forum topic has been bugging you. Write a short, pointed post about that one thing.",
                "Share one piece of news or information relevant to the forum. React to it in your voice.",
                "Ask the community one specific question you genuinely want answered.",
                "Share one personal experience related to the forum topic. Stay on that story.",
                "Take one stance on a contested topic in this forum and argue it directly.",
                "Write a short rant about one specific thing you think people in this forum get wrong.",
                "Share one recommendation, tip, or piece of advice on a specific aspect of the forum topic.",
                "React to something frustrating or exciting you encountered related to the forum topic.",
                "Make one focused, concrete observation about the forum topic that you think is underappreciated.",
            ]
            thread_focus = random.choice(foci)

            recent_stimuli = [s.text for s in self.stimuli[-3:]] if self.stimuli else []

            create_thread = dspy.ChainOfThought(CreateThreadPrompt)

            thread_info = create_thread(
                user=user_data,
                forum=forum_data,
                thread_focus=thread_focus,
                recent_stimuli=recent_stimuli
            )

            thread = Thread(
                title=thread_info.title,
                author=user,
                created_tick=self._time
            )

            post = Post(
                thread=thread,
                author=user,
                content=thread_info.body,
                reply_to="",
                created_tick=self._time
            )

            added_threads.append(thread)
            added_posts.append(post)

        return added_threads, added_posts
