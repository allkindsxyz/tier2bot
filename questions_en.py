"""
English questions for the test
"""

def validate_all_questions():
    """
    Validates that all questions have the correct format
    """
    for i, question in enumerate(ALL_QUESTIONS, 1):
        assert "question" in question, f"Question {i} is missing 'question' field"
        assert "options" in question, f"Question {i} is missing 'options' field"
        assert len(question["options"]) == 4, f"Question {i} should have exactly 4 options"

ALL_QUESTIONS = [
    {
        "question": "*Question:*\n*After a retreat, you feel deep insights, but someone says it's just a temporary effect of the psyche. How do you react?*",
        "options": {
            "1": "I don't take it seriously - I experienced it, it can't be an illusion",
            "2": "I don't like hearing this, but I don't want to argue",
            "3": "I allow for this possibility, but my experience remains valuable to me",
            "4": "I'm interested in this view - it's important for me to understand what's behind my feelings"
        }
    },
    
    {
        "question": "*Question:*\n*Evaluate the statement: we should live in the flow and enjoy the moment.*",
        "options": {
            "1": "Completely agree, why complicate life?",
            "2": "Generally agree, but it's important that this doesn't become an escape from reality",
            "3": "Rather disagree, pleasure is not the goal, but a side effect of deep understanding",
            "4": "Disagree, life is not only about joy, but also about awareness of complex and unpleasant things"
        }
    },
   
    {
        "question": "*Question:*\n*Your partner expects one thing from you, but you feel you need something else. What will you do?*",
        "options": {
            "1": "I'll try to adapt, because harmony is the main thing in relationships",
            "2": "I'll talk openly about our expectations and try to find a compromise",
            "3": "If our views are too different, maybe we're just not meant to be together",
            "4": "I'll think about what's behind his and my expectations, and try to understand how to reconcile them more deeply"
        }
    },
    
    {
        "question": "*Question:*\n*Someone in your group claims to be smarter than others. How do you react to this?*",
        "options": {
            "1": "It irritates me - such statements go against the values of equality and acceptance",
            "2": "I don't like it, but maybe there's something to learn from them",
            "3": "I wonder why it bothers me - maybe there's some truth in their words?",
            "4": "Calmly, everyone follows their own path, maybe it's actually true"
        }
    },
    
    {
        "question": "*Question:*\n*Will you speak out on politics, knowing your opinion doesn't match the majority?*",
        "options": {
            "1": "No, I don't want to provoke conflict and destroy harmony in communication",
            "2": "Only if I'm sure I'll be listened to without judgment",
            "3": "Yes, but I'll try to speak softly so as not to cause aggression",
            "4": "Yes, open discussion is important, even if my opinion is unpopular"
        }
    },
   
    {
        "question": "*Question:*\n*During a discussion, you notice that participants agree with each other more than they seek truth. What do you do?*",
        "options": {
            "1": "It irritates me, because such a discussion is meaningless",
            "2": "I feel uncomfortable, but I don't want to ruin the atmosphere",
            "3": "I carefully raise questions that might broaden the discussion",
            "4": "I observe and analyze - sometimes a sense of unity is more important to people than truth"
        }
    },
    
    {
        "question": "*Question:*\n*What do you feel when you see obvious injustice?*",
        "options": {
            "1": "It's terrible! Something must be done to restore justice",
            "2": "It's wrong, but the world, unfortunately, is not perfect",
            "3": "Justice is a subjective concept, and perhaps this situation has reasons I don't see",
            "4": "I wonder what forces and beliefs created this situation, and what can be changed in the long term?"
        }
    },
    
    {
        "question": "*Question:*\n*What role does intuition play in making important decisions?*",
        "options": {
            "1": "Intuition is the main thing, the universe knows better, and the mind is often limited",
            "2": "It's important to listen to intuition, but also to test it in practice",
            "3": "Intuition often fails if not supported by real data",
            "4": "Intuition is just quick processing of accumulated experience. It's important to understand where it comes from"
        }
    },
    
    {
        "question": "*Question:*\n*How do you feel about \"subtle energies\"?*",
        "options": {
            "1": "They play a key role in life, and I try to feel and direct them",
            "2": "I'm open to this, but it's important for me that personal experience confirms their existence",
            "3": "I see them more as a metaphor for processes occurring in the psyche and body",
            "4": "I tend to test such concepts in practice and analyze them from different perspectives"
        }
    },
    
    {
        "question": "*Question:*\n*You are in a group where people avoid discussing difficult or unpleasant topics. How do you perceive this?*",
        "options": {
            "1": "It irritates me, because without honesty nothing can be changed",
            "2": "I feel uncomfortable, but I don't want to ruin the harmony",
            "3": "I carefully raise difficult questions to stimulate discussion",
            "4": "I understand that everyone has their own pace, and not everyone is ready for such topics"
        }
    },
    
    {
        "question": "*Question:*\n*Your friend is facing a serious problem, but instead of taking concrete actions, they resort to meditation, manifestations, and appealing to the universe. What do you think about this?*",
        "options": {
            "1": "It's their choice, one cannot judge",
            "2": "I'll try to gently guide them towards actions without destroying their faith in spiritual practices",
            "3": "Most likely, they're just afraid to take responsibility and are looking for an excuse for inaction",
            "4": "Maybe it's important for them to go through this stage before they understand that actions are needed?"
        }
    },
    
    {
        "question": "*Question:*\n*Your friend said that to solve your problem, you just need to open your heart chakra. How do you perceive this?*",
        "options": {
            "1": "I'll completely agree, because inner state determines everything",
            "2": "I'll take note, but additionally look for more practical ways to solve the problem",
            "3": "I'll listen, but wonder if this is an escape from real actions",
            "4": "I'll ask for more details and ask: how is this related to the real cause of the problem?"
        }
    },
    
    {
        "question": "*Question:*\n*In a discussion, you notice that people confirm each other's views more than they actually seek truth. What do you do?*",
        "options": {
            "1": "This is normal, the main thing is support and unity",
            "2": "I'll try to gently direct the conversation in a deeper direction",
            "3": "I understand that this is more of a ritual of agreement than a search for truth, and decide if I want to participate in it",
            "4": "I observe why this unity is important to them, and think about how more depth could be introduced"
        }
    },
    
    {
        "question": "*Question:*\n*What do you feel when people say everyone has their own opinion, but get angry if someone thinks differently?*",
        "options": {
            "1": "It irritates me - they contradict their own words",
            "2": "I don't like it, but I try not to pay attention",
            "3": "I wonder, perhaps they just don't realize their reaction",
            "4": "I calmly accept it as part of human nature"
        }
    },
    
    {
        "question": "*Question:*\n*You notice that people talk a lot about compassion, but still divide the world into 'right' and 'wrong'. Why does this happen?*",
        "options": {
            "1": "They are hypocrites, their compassion is just a beautiful mask",
            "2": "They are sincere, but don't yet realize their contradictions",
            "3": "That's how human psychology works - it's difficult to go beyond dividing into 'us' and 'them'",
            "4": "This is a natural stage of development. Over time, many learn to see more broadly"
        }
    },
    
    {
        "question": "*Question:*\n*Someone uses ideas of mindfulness and spirituality for manipulation (for example, suppresses disagreement with phrases like \"you just don't understand the truth\"). What do you do?*",
        "options": {
            "1": "I get indignant and point out their manipulation to protect the truth",
            "2": "I feel irritated, but understand that arguing is useless",
            "3": "I try to understand why the person is doing this, and if possible, carefully ask questions",
            "4": "I accept that people use spirituality in different ways, and simply choose whether I should continue interacting with them"
        }
    },
    
    {
        "question": "*Question:*\n*Your friend suggested participating in a garbage collection project. How do you feel about such an idea?*",
        "options": {
            "1": "I'll gladly join! This is an important cause for society and ecology",
            "2": "I'll support the idea, but only if I see that the project really makes sense and has a long-term effect",
            "3": "First, I'll figure out how this solves the problem at its root, not just eliminates the consequences",
            "4": "I'll be respectful, but choose another way to solve the problem - through systemic changes, not one-time actions"
        }
    },
    
    {
        "question": "*Question:*\n*You try a new spiritual practice (meditation, yoga, energy exercises), but after several months you don't feel any changes. How do you react?*",
        "options": {
            "1": "I think I'm doing something wrong, and try to practice more diligently",
            "2": "I assume that changes are happening at a deep level, I just don't realize them yet",
            "3": "I begin to doubt the effectiveness of the practice and look for more rational explanations",
            "4": "I evaluate the practice critically, but without disappointment - I understand that not everything works for everyone"
        }
    },
    
    {
        "question": "*Question:*\n*You meet a person who is completely sure that their spiritual path is the only right one. What do you feel?*",
        "options": {
            "1": "Everyone has their own truth, and I respect their path",
            "2": "It's a pity that they limit themselves so much, because all paths are valuable",
            "3": "Perhaps they just haven't faced doubts or are afraid of them?",
            "4": "I wonder why they are so sure? Maybe they have valuable ideas?"
        }
    },
    
    {
        "question": "*Question:*\n*Your acquaintance says they've experienced a powerful spiritual experience and now they've \"seen the light\". How do you feel about this?*",
        "options": {
            "1": "That's wonderful! Every spiritual experience is valuable and leads to growth",
            "2": "I'm happy for them! I wonder what new truths they've discovered?",
            "3": "Most likely, this is just an emotional surge that will pass",
            "4": "I'll see how this changes their everyday decisions, not just their words"
        }
    },
    
    {
        "question": "*Question:*\n*You find yourself in a spiritual community where there's an atmosphere of love and support, but there are unspoken rules of hierarchy. How do you feel?*",
        "options": {
            "1": "I think it's natural - every system has its own laws",
            "2": "I feel slight discomfort, but try not to give it importance",
            "3": "I start to observe whether the community is really free, or if it's just a new form of control",
            "4": "I realize that spirituality doesn't require external structures, and look for a balance between communication and personal freedom"
        }
    },
    
    {
        "question": "*Question:*\n*You see someone using \"spiritual\" principles to justify their passivity and escape from reality. What do you think?*",
        "options": {
            "1": "Everyone has their own path, and you can't judge someone else's choice",
            "2": "It irritates me, because spirituality should lead to development, not to avoiding reality",
            "3": "I understand that this happens, but I see that judgment is unlikely to help - it's more important to understand why the person chose this path",
            "4": "I accept that people have different ways of coping with reality, but for myself I choose a path of responsibility and awareness"
        }
    },
    
    {
        "question": "*Question:*\n*You suddenly realize that, despite years of spiritual searching, you're still troubled by the same life questions. How do you perceive this?*",
        "options": {
            "1": "I think I just haven't reached the necessary level yet",
            "2": "I begin to doubt my path and the methods I've used",
            "3": "I understand that the very fact of \"searching\" might be the cause of my anxiety",
            "4": "I stop expecting \"solutions\" from spirituality and start living more consciously here and now"
        }
    },
    
    {
        "question": "*Question:*\n*Which of these principles is closest to you?*",
        "options": {
            "1": "One should strive for higher states of consciousness to be truly free",
            "2": "A person develops through experience, but there are more \"correct\" and \"pure\" paths",
            "3": "There is no single path, it's important to understand your true motives and limitations",
            "4": "Any concept is just a map, not the territory itself, and any principles can be revised"
        }
    },
    
    {
        "question": "*Question:*\n*When you encounter an opinion that completely contradicts yours, what happens first?*",
        "options": {
            "1": "I feel irritation and mentally look for arguments against it",
            "2": "I feel uneasy, but I'm ready to at least listen",
            "3": "I catch myself being interested: why does this person think this way?",
            "4": "It's important for me not only to understand their point of view, but also to identify the context in which it works"
        }
    },
    
    {
        "question": "*Question:*\n*You've been invited to a group that discusses a complex social problem, but you see that most participants hold a naive, simplified view. What do you do?*",
        "options": {
            "1": "I listen, don't interfere - everyone has their own truth",
            "2": "I'll try to gently explain to them a deeper view",
            "3": "I realize that the discussion is useless, and either leave or accept the rules of the game",
            "4": "I analyze the situation: is it worth sharing my thoughts or better to observe the group dynamics?"
        }
    },
    
    {
        "question": "*Question:*\n*Which of these principles seems most fair to you?*",
        "options": {
            "1": "People should be equal, and society should care for everyone",
            "2": "Freedom is most important, everyone is responsible for their own fate",
            "3": "It depends on the situation: sometimes equality is more important, sometimes freedom",
            "4": "Any idea only works in a certain context, and you need to be able to combine them"
        }
    },
    
    {
        "question": "*Question:*\n*What's more important to you in decision making?*",
        "options": {
            "1": "My feelings and intuition - they will suggest the right path",
            "2": "Harmony with others - it's important to consider the opinions and feelings of others",
            "3": "Analysis of the situation and possible consequences to avoid mistakes",
            "4": "A combination of logic, intuition, and systemic view - it's important to consider different perspectives"
        }
    },
    
    {
        "question": "*Question:*\n*How do you feel about a person who claims that your beliefs are naive?*",
        "options": {
            "1": "Everyone has the right to their opinion, and I don't see the point in arguing",
            "2": "This person just doesn't understand the depth of my beliefs",
            "3": "Perhaps there's some truth in their words, it's worth figuring out",
            "4": "I would find out why they think so and check my views"
        }
    },
    
    {
        "question": "*Question:*\n*What does 'being a wise person' mean to you?*",
        "options": {
            "1": "Living in harmony with yourself and others, accepting the world as it is",
            "2": "Having deep knowledge and sharing it with others",
            "3": "Being able to see situations from different sides, understanding causes and consequences",
            "4": "Flexibly adapting to complex systems, finding a balance between knowledge, intuition, and actions"
        }
    }
]

validate_all_questions() 