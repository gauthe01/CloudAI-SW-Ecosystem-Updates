# Feature 25 - Presenter Chatbot Rulebook Interview

## Status

Planned.

## Objective

Create an interview-style feature that asks the product owner targeted
questions and turns the validated answers into a precise rulebook for the
Presenter Ask AI chatbot.

## Why This Exists

The presenter chatbot needs rules that match the product owner's actual review
style, not generic AI behavior. The interview flow should collect those rules
directly and make them reviewable before they are applied to the chatbot.

## Required Behavior

- Start an interview from the Presenter Ask AI area without changing normal Ask
  AI behavior.
- Ask one focused rulebook question at a time.
- Save each answer as a draft rulebook decision.
- Let the product owner edit or reject each captured decision.
- Show a generated rulebook preview before anything becomes active.
- Keep the active chatbot rulebook unchanged until the product owner explicitly
  approves the generated version.

## Interview Topics

- What source types the chatbot may use.
- Whether answers can use approved updates only, metadata, source links, or
  broader connected-source history.
- How to respond when the answer is not available in the selected scope.
- Preferred answer length and formatting.
- How to handle quantitative facts, dates, owners, blockers, dependencies, and
  links.
- Whether risks, asks, and decisions should be answered only from explicit
  source text or can be inferred from approved updates.
- What wording should be avoided.
- What examples count as good and bad chatbot answers.

## First Interview Draft

1. Should Presenter Ask AI always answer from approved updates only, or should
   there be a separate mode that can include partner metadata?
2. If a user asks a question that approved updates cannot answer, should the
   chatbot always use exactly: "I do not see that in the selected approved
   updates."?
3. Should the chatbot show sources on every answer, only when source links are
   available, or only when the user asks?
4. Should the chatbot summarize multiple approved updates into one paragraph,
   or prefer bullets whenever more than one fact is involved?
5. Are there words or phrases the chatbot should never use in presenter-facing
   answers?

## Implementation Notes

- Add a separate interview mode or modal so normal presenter questions remain
  unaffected.
- Store interview answers as draft rulebook data, not as active prompt text.
- Generate a markdown rulebook preview from the accepted answers.
- Add an explicit "Apply rulebook" action guarded by confirmation.
- Keep a version history for generated rulebooks so changes are auditable.

## Acceptance Criteria

- The product owner can start, pause, and resume the rulebook interview.
- Captured answers are visible and editable before rulebook generation.
- The generated rulebook is previewed as markdown.
- The active chatbot rulebook changes only after explicit approval.
- The chatbot continues to answer from its current approved rulebook until the
  new rulebook is approved.
