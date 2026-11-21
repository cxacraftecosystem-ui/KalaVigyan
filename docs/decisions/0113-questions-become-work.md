# 0113. Questions KalaVigyan cannot answer well become open work

Date: 2026-11-21. Status: accepted (owner, 2026-11-21: "A question the knowledge can't answer well
should open a task in open work automatically. That closes the loop between readers and
contributors; today the two halves don't connect."). Adds a task kind to decision 0101's open work
(item 15); the gates, reservations and the review switch stand.

## Context

Readers ask; contributors research. Both halves existed, but nothing carried what readers could not
learn to the people who could fill it. An answer already records its fields, its cited sentences,
its cited facts and the evidence its research packs held, so how well each question was answered can
be judged without another model call. The questions themselves are personal data: they hold names,
numbers and sometimes questions about other people, and open work is listed to anyone, signed in or
not, and to every MCP client.

## Decision

1. **Every finished answer gets a verdict**, from what it already holds and no model call: for each
   field it answered, its cited sentences at a fact level, whether its research found a stored fact
   matching the question's words or names (a best fused score above 1/61, the most one ranking alone
   can give with `RRF_K` 60 and a ranking depth of 30), and whether it cited a fact with a failed
   quote. `UNANSWERED` when no field holds a cited sentence; `THIN` when a field holds none or fewer
   than 3, scored low, or cited a failed quote; `ANSWERED` otherwise. The verdict, its fields and the
   craft are kept in `AnswerVerdict`, written in the transaction that finishes the answer. A section
   reused from stored pieces is not judged on retrieval, because no retrieval ran for it.
2. **The nightly upkeep groups thin and unanswered questions about a craft by meaning.** Each
   anonymised question is embedded once and joins the nearest open group of its craft within a cosine
   distance of 0.15, or opens one. A group counts the distinct accounts that asked within 90 days,
   lists the fields its members lacked and what they lacked, and takes its priority from how many
   asked and how recently: `HIGH` for 5 or more with the latest within 30 days, `MEDIUM` for 5 or more
   earlier or 2 or more within 30 days, `LOW` otherwise. A group no one asked within 90 days lapses.
3. **Each open group is an `ANSWER_GAP` task** of its craft or family, listed after the subject's
   healing tasks with the `research_field` prompt for its first field. Its acceptance is checked by a
   retrieval run, not a model: the stored search over the craft and each field, with the group's
   question as text and its stored vector as the query vector, must find at least 2 cited facts at a
   fact level matched by the question's words or names (by meaning alone for a question not in an
   English script). The task then closes itself and a live reservation of it ends `COMPLETED`.
4. **The privacy rule.** A task never says who asked: it carries a count, never an account, an
   answer or a conversation, and the asker's identity never leaves the answer rows it already lived
   in. The question shown is anonymised by fixed rules, with no model:
   - a question asking for someone's contact (a phone, mobile, WhatsApp or contact number, an email
     or address of someone, a home address, how to reach someone) is dropped whole;
   - a question that names someone (a name after an honorific, or two or more capitalised words not
     all in a craft, category, family, state or district name) and asks about them (who they are,
     their life, age, marriage, home, family, income, caste, religion or health) is dropped whole: it
     is a question about a person, never research;
   - otherwise emails, links, handles, phone numbers, PIN codes, house numbers, street addresses, the
     asker's own name after a self-introduction, names after honorifics (English and Hindi) and
     unknown runs of capitalised words are replaced by `[email]`, `[link]`, `[name]`, `[phone]` and
     `[address]`;
   - what keeps fewer than 3 words is dropped.
   The verdict and group tables have row level security and no grants to the public roles.

## Consequences

- Readers' demand reaches contributors by itself, ranked by how many asked, and heals itself: a
  group whose facts arrive, by any route, closes at the next night.
- The rules over-remove rather than leak: a place outside the gazetteer written in capitals becomes
  `[name]`, and a title-cased question may be dropped. A single first name with no honorific or
  self-introduction is not detected; the run of capitals, the honorifics and the asks about a person
  cover the forms seen in questions, and the rules are tested case by case.
- A fact cannot name an `ANSWER_GAP` task as its `task_key` (the fact path completes field and
  corroboration tasks only), so a contributor names the field's task when one is open and the gap
  closes at its nightly check; a fact path that completes the gap at once is a later change to
  `research/knowledge_writes.fact_task_problem`.
- Embedding the questions is the one new call: once per question, in batches, at night; when it fails
  the night goes on with the vectors it has.
- A question about no craft keeps its verdict but opens no task, since acceptance is a retrieval run
  over one craft.
