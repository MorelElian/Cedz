# Peloton Ranking and Question Design

## Goal

Make revealed ranking opinions comparable across the Peloton, enrich ranking answers with one optional comment per ranked person, add a three-person free-answer question type, and make Peloton revelation lists bounded and chronological.

## Ranking model

Each ranking answer retains `ordered_participant_ids` and `lap_time`, and gains `participant_comments`, a mapping from participant id to an optional 1,000-character comment. Existing answers without this mapping behave as an empty mapping.

Only revelations with `status='sent'` count toward averages. For each discipline and globally, the app averages each participant's revealed positions, orders participants ascending by that mean, and exposes a one-based rank plus the mean and opinion count. Ties receive the same rank.

When a ranking revelation is rendered, it keeps the existing position wording and appends only the comment for the recipient when it exists.

## Question type

`three_person_free_text` targets exactly three randomly selected participants and stores one free-text answer. The same answer can create a candidate revelation for each of those participants. It is selectable in admin creation and participant suggestions; suggestions require `{person1}`, `{person2}`, and `{person3}`.

## Peloton lists

The profile endpoint returns the five newest sent revelations for first render and accepts pagination for older sent revelations in descending chronological order. A client-side “Charger plus de réponses” action loads the next page without duplicating cards.

The interaction section contains at most five revelations with at least one interaction, ranked by reaction count plus comment count, then by sent time. It is separate from the five newest revelations.

## Compatibility and validation

No destructive migration is required. Missing `participant_comments` are normalized to an empty mapping. All incoming participant ids must be active and ranking comments must be strings of at most 1,000 characters.
