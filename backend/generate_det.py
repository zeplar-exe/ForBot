from PIL import Image, ImageDraw
import random
import matplotlib.pyplot as plt
from collections import defaultdict

USERNAME_CORPUS = []

with open("res/usernames.txt", "r") as f:
    for line in f:
        USERNAME_CORPUS.append(line.strip())

def _build_ngram_chain(corpus, n=3):
    """Build an (n-1)-gram character chain with start/end markers.
    Returns: dict mapping state(tuple) -> list of next chars
    """
    chain = defaultdict(list)
    for word in corpus:
        w = word.strip().lower()
        
        if not w:
            continue
        
        padded = ("^" * (n - 1)) + w + "$"
        
        for i in range(len(padded) - (n - 1)):
            state = tuple(padded[i:i + (n - 1)])
            next_char = padded[i + (n - 1)]
            chain[state].append(next_char)
    
    return chain


def _sample_with_backoff(chain, state):
    """Sample a next char for `state` using backoff to shorter contexts.
    `state` is a tuple. If no match, drop the leftmost symbol and retry.
    If nothing matches, return None.
    """
    s = tuple(state)
    while s:
        if s in chain and chain[s]:
            return random.choice(chain[s])
        s = s[1:]
        
    if tuple() in chain and chain[tuple()]:
        return random.choice(chain[tuple()])
    
    return None


def generate_username(max_length=12, n=3, candidates=25):
    """Generate a username using an n-gram character model with backoff.

    - `n` is the n-gram order (3 => bigram state -> next char)
    - Returns a single generated username (capitalized)
    """
    chain = _build_ngram_chain(USERNAME_CORPUS, n=n)

    if not chain:
        return random.choice(USERNAME_CORPUS).capitalize()

    gen_list = []
    for _ in range(candidates):
        state = tuple("^" * (n - 1))
        chars = []
        
        while True:
            next_c = _sample_with_backoff(chain, state)
            if next_c is None:
                break
            if next_c == "$":
                break
            chars.append(next_c)
            state = tuple(("".join(state) + next_c)[- (n - 1):])
            
            if len(chars) >= max_length:
                break

        candidate = ''.join(chars)
        
        if 2 <= len(candidate) <= max_length and candidate.isalnum():
            gen_list.append(candidate.capitalize())

    gen_list = list(dict.fromkeys(gen_list))
    
    if gen_list:
        return random.choice(gen_list)
    
    base = random.choice(USERNAME_CORPUS)
    
    if len(base) < max_length:
        base = base + str(random.randint(0, 99))
    
    return base.capitalize()

def generate_profile_picture(w=256, h=256):
    bg_color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
    img = Image.new('RGB', (w, h), bg_color)
    draw = ImageDraw.Draw(img)
    
    num_shapes = random.randint(5, 15)
    
    for _ in range(num_shapes):
        shape_type = random.choice(['rectangle', 'oval', 'triangle'])
        color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        
        if shape_type == 'rectangle':
            x1 = random.randint(0, w)
            y1 = random.randint(0, h)
            x2 = random.randint(x1, w)
            y2 = random.randint(y1, h)
            draw.rectangle([x1, y1, x2, y2], fill=color)
        
        elif shape_type == 'oval':
            x1 = random.randint(0, w)
            y1 = random.randint(0, h)
            x2 = random.randint(x1, w)
            y2 = random.randint(y1, h)
            draw.ellipse([x1, y1, x2, y2], fill=color)
        
        elif shape_type == 'triangle':
            points = [
                (random.randint(0, w), random.randint(0, h)),
                (random.randint(0, w), random.randint(0, h)),
                (random.randint(0, w), random.randint(0, h))
            ]
            draw.polygon(points, fill=color)
    
    return img


if __name__ == "__main__":
    for _ in range(5):
        print(generate_username())
    
    profile_pic = generate_profile_picture(256, 256)
    plt.figure(figsize=(6, 6))
    plt.imshow(profile_pic)
    plt.axis('off')
    plt.title("Random Profile Picture")
    plt.tight_layout()
    plt.show()