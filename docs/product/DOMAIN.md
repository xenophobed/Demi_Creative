# Kids Creative Workshop - Domain Background

## 1. Domain Overview

### 1.1 Problem Space

**Current pain points in the children's content space**:
1. **Limited creative expression**: Children have rich imaginations but lack the ability to turn imagination into complete stories
2. **Content safety risks**: The internet is flooded with content unsuitable for children, causing parental concern about content safety
3. **Insufficient personalization**: Children's content on the market is mostly standardized products, lacking personalization
4. **Passive consumption**: Traditional storybooks and cartoons are one-directional output; children lack a sense of participation
5. **Knowledge access barriers**: News and knowledge from the adult world is too complex for children

### 1.2 Solution

Leveraging **AI Agent technology** to build an intelligent children's content creation platform:
- Transform children's drawings into stories
- Generate interactive personalized stories
- Convert adult news into child-friendly content
- Provide safe, fun, and educational content

---

## 2. Core Domain Concepts

### 2.1 Child Development Stages

#### Ages 3-5 (Preschool)
- **Cognitive Traits**: Concrete thinking, enjoys repetition, short attention span
- **Language Ability**: Simple sentences, common vocabulary of 500-2000 words
- **Interests**: Animals, family, simple adventures
- **Content Requirements**: Short stories (100-200 words), simple language, clear endings

#### Ages 6-8 (Early Elementary)
- **Cognitive Traits**: Beginning logical thinking, strong curiosity, enjoys exploration
- **Language Ability**: Complex sentences, vocabulary of 3000-5000 words
- **Interests**: Dinosaurs, space, magic, friendship
- **Content Requirements**: Medium stories (200-400 words), can include simple plot twists

#### Ages 9-12 (Upper Elementary)
- **Cognitive Traits**: Enhanced abstract thinking, beginning critical thinking
- **Language Ability**: Rich expression, vocabulary of 5000-8000 words
- **Interests**: Science, history, complex adventures, interpersonal relationships
- **Content Requirements**: Longer stories (400-800 words), can include multi-thread narratives

### 2.2 Content Safety Standards

#### Negative Content Filtering
- **Violence**: Fighting, blood, weapon use
- **Horror**: Ghosts, darkness, thriller elements
- **Inappropriate Language**: Profanity, insulting words, discriminatory expressions
- **Adult Topics**: Sex, drugs, alcoholism, political controversy

#### Positive Value Guidance
- **Gender Equality**: Avoid stereotypes (e.g. "girls should be gentle, boys should be brave")
- **Cultural Diversity**: Represent different cultures, races, and family structures
- **Character Education**: Friendship, courage, honesty, empathy, responsibility
- **Inclusivity**: Respect people of different abilities, appearances, and backgrounds

### 2.3 Educational Goals

#### STEAM Education
- **Science**: Inspire curiosity about nature and science
- **Technology**: Understand how technology changes the world
- **Engineering**: Develop problem-solving thinking
- **Arts**: Encourage creative expression
- **Math**: Integrate mathematical concepts into stories

#### Character Education
- **Friendship**: How to make friends and maintain friendships
- **Courage**: Not backing down when facing difficulties
- **Honesty**: The importance of telling the truth
- **Empathy**: Understanding others' feelings
- **Responsibility**: Being accountable for one's actions

---

## 3. Technical Domain Concepts

### 3.1 AI Agent Architecture

#### Agent Definition
An **Agent** is an autonomous intelligent entity that can:
- Perceive the environment (receive input)
- Make autonomous decisions (choose which tools to use)
- Execute actions (call tools to complete tasks)
- Learn from feedback (adjust strategy based on results)

#### Agent vs Traditional API
```
Traditional API:
  Input → Fixed processing logic → Output

AI Agent:
  Input → Agent reasoning → Select tools → Execute → Evaluate results → Output
          ↑___________________________________|（may iterate multiple rounds）
```

### 3.2 Core Agent Roles

#### 1. ImageAnalysisAgent (Drawing Analyst)
**Responsibility**: Understand the meaning of children's drawings

**Tools (Skills)**:
- `vision_analyze`: Call Claude Vision API to identify drawing elements
- `vector_search`: Search for similar drawings in vector database
- `emotion_detect`: Analyze drawing mood and atmosphere

**Input**: Drawing image + child information
**Output**: Drawing description (objects, scene, mood, recurring characters)

#### 2. StoryGeneratorAgent (Story Creator)
**Responsibility**: Create age-appropriate stories for children

**Tools (Skills)**:
- `story_template`: Use story templates
- `age_adapter`: Adjust language complexity based on age
- `branch_generator`: Generate interactive branches (interactive mode)
- `tts_generate`: Generate audio narration

**Input**: Drawing analysis results / interest tags + child's age
**Output**: Story text + audio + interactive options

#### 3. MorningShowAgent (Morning Show Host)
**Responsibility**: Transform news into dual-character dialogue podcasts, integrating children's characters from the memory system

**Tools (Skills)**:
- `dialogue_script_generator`: Generate Curious Kid + Fun Expert dialogue scripts
- `character_injector`: Query recurring characters from Memory System and inject as guest hosts
- `multi_speaker_tts`: Orchestrate multi-character TTS generation (different voice parameters)
- `illustration_generator`: Generate 3-4 accompanying illustrations based on news themes
- `simplify_language`: Language simplification (using metaphors, everyday vocabulary)
- `concept_explainer`: Explain complex concepts

**Input**: News URL/text + target age + subscription channels + child preferences
**Output**: Dialogue script + multi-character audio + illustrations + child-friendly title/concepts/interactive questions

> Note: Original NewsConverterAgent retained as manual mode/fallback

#### 4. SafetyAgent (Content Reviewer)
**Responsibility**: Ensure all content is safe and values-aligned

**Tools (Skills)**:
- `content_filter`: Negative content filtering
- `bias_detector`: Detect gender and cultural bias
- `sentiment_analysis`: Sentiment analysis
- `value_checker`: Values check

**Input**: Content to review + target age
**Output**: Safety score + issue list + modification suggestions

#### 5. MemoryAgent (Memory Manager)
**Responsibility**: Manage children's creation history and preferences

**Tools (Skills)**:
- `embedding_create`: Generate content vectors
- `vector_store`: Store in vector database
- `similarity_search`: Similarity search
- `preference_track`: Track preference changes

**Input**: Content + user ID
**Output**: Related historical records + preference tags

---

## 4. Domain Rules

### 4.1 Age Adaptation Rules

```yaml
Ages 3-5:
  Vocabulary: Simple nouns and verbs
  Sentence structure: Subject-verb-object, no more than 10 words
  Story length: 100-200 words
  Themes: Daily life, animals, simple adventures
  Ending: Must be clear and positive

Ages 6-8:
  Vocabulary: Common words + adjectives
  Sentence structure: Compound sentences allowed, moderate rhetoric
  Story length: 200-400 words
  Themes: Friendship, exploration, magic, science
  Ending: Can have minor twists, but must be positive

Ages 9-12:
  Vocabulary: Rich vocabulary + idioms
  Sentence structure: Complex sentences, varied rhetoric
  Story length: 400-800 words
  Themes: Complex plots, multi-thread narratives, deep thinking
  Ending: Can be open-ended, thought-provoking
```

### 4.2 Interactive Story Rules

```yaml
Decision point setup:
  - Count: 2-4 decision points per story
  - Interval: One every 100-150 words
  - Options: 2-3 options per decision point
  - Consequence: All options lead to "good endings" (never punish children's choices)

Option design:
  - Clarity: Option text is clear, children can understand
  - Contrast: Clear distinction between options (e.g. brave vs cautious)
  - Fun: Use emoji to add fun
  - Educational: Each option has educational value behind it
```

### 4.3 Content Continuity Rules

```yaml
Character memory:
  - Recognize recurring characters: e.g. child draws "Lightning the puppy" multiple times
  - Maintain character consistency: "Lightning the puppy"'s traits persist across stories
  - Character growth: Over time, characters can "grow"

Story associations:
  - Historical references: "Do you remember Lightning the puppy's adventure last time?"
  - Theme continuity: If child enjoys space themes, prioritize recommending those in future stories
  - Learning progression: Gradually increase difficulty based on child feedback
```

---

## 5. Key Glossary

### Agent-Related
- **Agent**: Autonomous intelligent entity capable of perceiving, deciding, and executing
- **Tool/Skill**: Tools/abilities that an Agent can use
- **System Prompt**: Instructions that define an Agent's role and behavior
- **Multi-turn**: Multi-round dialogue; Agent can complete tasks in steps

### Content-Related
- **Interactive Story**: Story where children can make choices at key points
- **Branch**: Story branch; different choices lead to different plot lines
- **Linear Story**: Traditional single-thread narrative
- **TTS (Text-to-Speech)**: Text to speech conversion
- **Dynamic Picture Book**: Animated picture book that brings static drawing elements to life
- **Morning Show**: Dual-character dialogue podcast format for news content
- **Dialogue Script**: Structured script annotated with character roles and lines
- **Animatic**: Animated illustration; static images with Ken Burns pan/zoom animation simulating video effect
- **Daily Drop**: Daily delivery; episodes auto-generated on schedule for subscribed channels
- **Topic Subscription**: Channel subscription; children select news categories of interest to automatically receive content

### Technology-Related
- **Vector Database**: Database for storing and searching high-dimensional vectors
- **Embedding**: Vector embedding; converting text/images into numerical vectors
- **Similarity Search**: Finding similar content based on vector proximity
- **Contract Testing**: Tests that define input/output specifications

### Children's Education-Related
- **COPPA**: Children's Online Privacy Protection Act
- **Age-appropriate**: Content suitable for the target age group
- **STEAM**: Integrated education across Science, Technology, Engineering, Arts, and Mathematics
- **Social-Emotional Learning**: Learning focused on social and emotional development

---

## 6. Business Scenario Examples

### Scenario 1: Image-to-Story
```
Xiaoming (age 7) drew a picture:
- Scene: A puppy under a tree, with sun and clouds nearby
- Mood: Happy, warm

Agent workflow:
1. ImageAnalysisAgent analyzes:
   - Identifies: puppy, tree, sun, clouds
   - Scene: outdoor park
   - Mood: happy, warm
   - Vector search: discovers Xiaoming drew a similar puppy last week, named "Lightning"

2. StoryGeneratorAgent creates story:
   "Lightning the puppy came to its favorite park again today. The warm sunlight
    shone down, and the leaves rustled softly in the breeze. Lightning wagged its tail happily..."
   (Suitable for age 7, 200 words, incorporating "Lightning" as a recurring character)

3. SafetyAgent review: ✅ Passed (no safety issues)

4. TTS generates audio: uses "gentle grandma" voice for narration

Output: story text + audio + illustration suggestions
```

### Scenario 2: Interactive Story Generation
```
Xiaohong (age 8) wants to hear a dinosaur story:
- Age: 8
- Interests: dinosaurs, science
- Mode: interactive

Agent workflow:
Round 1:
  Story: "The little dinosaur discovered a mysterious cave in the forest, with a strange light flickering at the entrance..."
  Choices:
    A. Bravely walk inside 🏔️
    B. Go home first and bring friends 👫

Xiaohong chooses A → Round 2:
  Story: "The little dinosaur gathered its courage and entered the cave, only to find a glowing fossil inside..."
  Choices:
    A. Study the fossil carefully 🔬
    B. Take the fossil home 🏠

... (continues for 3-5 rounds)

Final ending + educational highlights: courage, spirit of scientific exploration
```

### Scenario 3: News Morning Show
```
News: SpaceX successfully launches rocket to the moon
Xiaoming (age 7) subscribed to "Space" channel, has recurring character "Lightning the puppy"

MorningShowAgent generates morning show:
1. Generates dual-character dialogue script:
   Curious Kid: Hey! I heard someone launched a super huge bus to the moon?
   Fun Expert: That's right! Scientists built a giant rocket, taller than a 30-story building!
   Curious Kid: Wow, that's taller than our school! How did it fly up there?
   Fun Expert: It used super powerful engines that shot out blue and orange flames...

2. Memory System finds "Lightning the puppy" → injected as guest:
   [Lightning the Puppy]: Woof woof! I want to ride a rocket to the moon too! Are there bones on the moon?
   Fun Expert: Haha, there are no bones on the moon, but there are lots of craters...

3. Multi-character TTS: Curious Kid (shimmer) + Fun Expert (fable) + Lightning the Puppy (nova)

4. Generates 3 accompanying illustrations → Ken Burns animation → synchronized with dialogue segments

5. SafetyAgent review: ✅ Passed

Output: 2-minute morning show episode → auto-saved to "My Library"
```

---

## 7. Success Metrics

### Product Metrics
- **Usage Frequency**: Children use the platform 3+ times per week
- **Completion Rate**: Interactive story completion rate > 80%
- **Parent Satisfaction**: > 4.5/5.0
- **Content Safety**: Inappropriate content pass-through rate < 0.1%

### Educational Outcomes
- **Creativity**: Increase in children's proactive creation frequency
- **Reading Interest**: Increase in reading time
- **Knowledge Acquisition**: Children can explain complex concepts in their own words
- **Character Development**: Parents report improved child behavior

### Technical Metrics
- **Response Speed**: Story generation < 10 seconds
- **Accuracy**: Agent output matches contract > 95%
- **Safety**: Safety check pass rate 100%

---

## 8. References

### Child Development
- Piaget's Stages of Cognitive Development
- Vygotsky's Zone of Proximal Development
- Common Core State Standards (age-based reading standards)

### Content Safety
- COPPA (Children's Online Privacy Protection Act)
- GDPR-K (Children's Data Protection)
- ESRB Rating System (Entertainment Software Rating)

### AI Agent
- [Claude Agent SDK Documentation](https://docs.anthropic.com/agent-sdk)
- [Tool Use in Claude](https://docs.anthropic.com/claude/docs/tool-use)
- [Prompt Engineering for Children's Content](https://www.anthropic.com/research)
