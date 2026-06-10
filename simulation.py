from collections import defaultdict
from contextlib import nullcontext
from concurrent.futures import ThreadPoolExecutor

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
    Generate a set of real life details about a user with the given personality such as occupation, hobbies, 
    and other interests.
    """
    personality: str = dspy.InputField()
    real_life_details: list[str] = dspy.OutputField()

class GenerateVoiceProfilePrompt(dspy.Signature):
    """
    Generate a voice profile for a forum user as two lists:
    'examples': 3-4 short sentence starters that show exactly how this person opens a post —
        concrete, in-character, already written in their voice (e.g. "lol ok so here's the thing",
        "ngl im kinda salty about", "does anyone else feel like").
    'restrictions': 3-4 specific things this person never does when writing
        (e.g. "never capitalizes anything", "never uses full sentences", "never hedges opinions").
    Make examples and restrictions distinctive to this personality, not generic.
    """
    forum: ForumPromptData = dspy.InputField()
    personality: str = dspy.InputField()
    examples: list[str] = dspy.OutputField()
    restrictions: list[str] = dspy.OutputField()

class ThreadReasoningPrompt(dspy.Signature):
    """
    Think through how this user would react to this thread. Output pure reasoning — no post text.
    Be exhaustive: the write step will only see your outputs, not the thread itself.

    should_engage: whether this user would bother responding at all given their dedication,
        how many times they've already posted, and how much the thread interests them.
    reply_to: exact username of the person they are directly addressing, or empty string
        if they are speaking to the thread generally.
    emotional_reaction: specific, visceral reaction — not just a label ('annoyed') but
        what exactly triggered it and why this user in particular would feel that way.
    stance: full position — which specific claims in the thread they agree or disagree with,
        which arguments they find compelling or weak, and why their personality leads them there.
    key_point: detailed brief for the post — the argument they will make, any concrete example
        or reference they would use, the emotional register (rant, deadpan, enthusiastic, etc.),
        and how they want the reader to feel after reading it. Two to four sentences.
    """
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread_title: str = dspy.InputField()
    thread_summary: str = dspy.InputField()
    thread_post_history: str = dspy.InputField()
    relevant_users: list[dict] = dspy.InputField()
    relevant_documents: str = dspy.InputField()
    own_posts_count: int = dspy.InputField()
    total_posts_count: int = dspy.InputField()
    should_engage: bool = dspy.OutputField()
    reply_to: str = dspy.OutputField()
    emotional_reaction: str = dspy.OutputField()
    stance: str = dspy.OutputField()
    key_point: str = dspy.OutputField()

class WritePostPrompt(dspy.Signature):
    """
    Write a forum post as this user. You have been given their reasoning: the stance they hold,
    who they are replying to, and the single key point they want to make. Write the actual post
    in the user's voice — exactly as they would type it. One point, one voice, done.
    Never break character. No disclaimers or warnings.
    Do not quote, reference, or describe the voice profile — simply embody it.
    Do not pad with extra topics or opinions beyond the key point.
    """
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread_title: str = dspy.InputField()
    emotional_reaction: str = dspy.InputField()
    stance: str = dspy.InputField()
    key_point: str = dspy.InputField()
    reply_to_username: str = dspy.InputField()
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
    Do not reference, quote, or describe the user's voice profile or personality — simply embody it.
    """
    user: UserPromptData = dspy.InputField()
    forum: ForumPromptData = dspy.InputField()
    thread_focus: str = dspy.InputField()
    recent_stimuli: list[str] = dspy.InputField()
    title: str = dspy.OutputField()
    body: str = dspy.OutputField()

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
        self._posts_by_thread: dict[str, list[Post]] = defaultdict(list)
        self._posts_by_user: dict[str, list[Post]] = defaultdict(list)

    def _add_post(self, post: Post):
        self.posts.append(post)
        self._posts_by_thread[post.thread.id].append(post)
        self._posts_by_user[post.author.id].append(post)

    def _rebuild_index(self):
        self._posts_by_thread = defaultdict(list)
        self._posts_by_user = defaultdict(list)
        for post in self.posts:
            self._posts_by_thread[post.thread.id].append(post)
            self._posts_by_user[post.author.id].append(post)

    def get_user_threads(self, user: User) -> List[Thread]:
        return [thread for thread in self.threads if thread.author == user]

    def get_user_posts(self, user: User) -> List[Post]:
        return self._posts_by_user[user.id]

    def get_user_posts_in_thread(self, user: User, thread: Thread) -> List[Post]:
        return [p for p in self._posts_by_thread[thread.id] if p.author == user]

    def get_posts_in_thread(self, thread: Thread) -> List[Post]:
        return self._posts_by_thread[thread.id]

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

            voice_result = generate_voice(
                forum=forum_data,
                personality=personality,
            )
            examples_str = ", ".join(f'"{e.strip()}"' for e in voice_result.examples)
            restrictions_str = "; ".join(r.strip() for r in voice_result.restrictions)
            voice_profile = f"My posts sound like: {examples_str}. I never: {restrictions_str}."

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
        recent_post_strs = [f"{p.author.username}: {p.content[:300]}" for p in recent_posts]
        generate_summary = dspy.Predict(GenerateThreadSummaryPrompt)
        thread.summary = generate_summary(
            forum=ForumPromptData(name=self.forum.name, topic=self.forum.topic_summary),
            thread_title=thread.title,
            author_username=thread.author.username,
            previous_summary=thread.summary or "",
            recent_posts=recent_post_strs,
        ).summary
        self._logger.debug(f"Updated summary for thread '{thread.title}'")

    @mlflow.trace
    def advance_one_hour(self) -> tuple[List[Thread], List[Post]]:
        self._time += 1
        hour_threads: List[Thread] = []
        hour_posts: List[Post] = []
        threads_to_summarize: dict[str, Thread] = {}

        active_users = [
            u for u in self.users
            if u.active_hours[0] <= self._time % 24 < u.active_hours[1]
        ]

        posts_snapshot = list(self.posts)

        def process_user(user: User) -> tuple[List[Thread], List[Post]]:
            with self._lm_ctx:
                for attempt in range(3):
                    try:
                        return self._simulate_user_activity(user, posts_snapshot)
                    except Exception as e:
                        self._logger.warning(f"User {user.username} attempt {attempt + 1}/3 failed: {e}")
                        if attempt == 2:
                            self._logger.error(f"Skipping user {user.username} after 3 failed attempts")
                            return [], []

        with ThreadPoolExecutor(max_workers=4) as executor:
            all_results = list(executor.map(process_user, active_users))

        for (added_threads, added_posts), user in zip(all_results, active_users):
            hour_threads.extend(added_threads)
            hour_posts.extend(added_posts)
            self.threads.extend(added_threads)
            for post in added_posts:
                self._add_post(post)
                count = len(self.get_posts_in_thread(post.thread))
                if count % self.thread_summary_update_interval == 0:
                    threads_to_summarize[post.thread.id] = post.thread
            self._logger.debug(f"Simulated {user.username}: +{len(added_threads)} threads, +{len(added_posts)} posts")

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

    def _simulate_user_activity(self, user: User, posts: List[Post]) -> tuple[List[Thread], List[Post]]:
        if random.random() > user.forum_dedication:
            return [], []

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

        # Single-pass unseen filter + grouping
        threads: dict[str, list[Post]] = defaultdict(list)
        for post in posts:
            if post.id not in user.viewed_posts and post.author != user:
                threads[post.thread.id].append(post)

        # Hoist DSPy module instantiation outside the per-thread loop
        decide_view_thread = dspy.Predict(DecideViewThreadPrompt)
        thread_reasoning = dspy.Predict(ThreadReasoningPrompt)
        write_post = dspy.Predict(WritePostPrompt)
        generate_user_summary = dspy.Predict(GenerateUserSummaryPrompt)

        for thread_id, thread_posts in threads.items():
            thread = thread_posts[0].thread

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

            # Mark posts as viewed and track user summary update triggers
            for post in thread_posts:
                user.viewed_posts[post.id] = ViewedPost(
                    post_id=post.id,
                    view_date=self._time,
                    author_username=post.author.username,
                    summary=None
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
                    user_summary.summary = generate_user_summary(
                        self_user=user_data,
                        target_username=post.author.username,
                        forum=forum_data,
                        target_recent_posts=[{p.id: p.content} for p in self.get_user_posts(post.author)[:10]],
                        old_summary=user_summary.summary
                    ).new_summary
                    user_summary.last_updated = self._time

            all_thread_posts = self.get_posts_in_thread(thread)
            previous_posts = all_thread_posts[-10:]
            thread_post_history = '\n'.join(
                f"{p.author.username}: {p.content[:300]}" for p in previous_posts
            )

            thread_post_count = len(all_thread_posts)
            own_post_count = len(self.get_user_posts_in_thread(user, thread))

            unique_previous_users = set(p.author.id for p in previous_posts)
            relevant_users = [
                {"username": us.summarized_user_username, "summary": us.summary}
                for uid in unique_previous_users
                if (us := user.user_summaries.get(uid))
            ]

            relevant_documents = ""
            if thread.summary and self._document_embeddings is not None:
                relevant_documents = "\n".join(self._document_embeddings(thread.summary))

            reasoning = thread_reasoning(
                user=user_data,
                forum=forum_data,
                thread_title=thread.title,
                thread_summary=thread.summary or "",
                thread_post_history=thread_post_history,
                relevant_users=relevant_users,
                relevant_documents=relevant_documents,
                own_posts_count=own_post_count,
                total_posts_count=thread_post_count,
            )

            if not reasoning.should_engage:
                continue

            post_content = write_post(
                user=user_data,
                forum=forum_data,
                thread_title=thread.title,
                emotional_reaction=reasoning.emotional_reaction,
                stance=reasoning.stance,
                key_point=reasoning.key_point,
                reply_to_username=reasoning.reply_to,
            ).response

            added_posts.append(Post(
                thread=thread,
                author=user,
                content=post_content.strip(),
                reply_to=reasoning.reply_to.strip() if reasoning.reply_to else "",
                created_tick=self._time
            ))

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
