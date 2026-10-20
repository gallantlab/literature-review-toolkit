---
hide:
  - navigation
  - toc
---

<div class="hero" markdown>

<div class="hero-text" markdown>

# Literature reviews with no invented references

You describe the review you want in plain English. An AI agent searches the
literature, groups the papers into families of ideas, and can write the review
up. Scripts check every reference against the publishers' databases.

[Start the tutorial](tutorial.md){ .md-button .md-button--primary }
[See examples](examples.md){ .md-button }

<p class="hero-meta">Version 2.4.5 · MIT license · <a href="#ai-disclosure">AI disclosure</a></p>

</div>

<figure class="fig hero-fig" markdown>
![A timeline of 190 papers on how the brain represents complexity, in six family lanes from 1948 to 2026](assets/figures/lineage_complexity.png)
<figcaption markdown>
**A finished timeline:** 190 checked papers in six families of ideas, 1948–2026.
</figcaption>
</figure>

</div>

<div class="stats" markdown>
<div><span class="stat">1 in 4</span><span class="stat-label">citations an agent gets wrong from memory</span></div>
<div><span class="stat">0</span><span class="stat-label">references typed by the agent: each is rebuilt from its DOI</span></div>
<div><span class="stat">3</span><span class="stat-label">decisions left to you: scope, families, write-up</span></div>
</div>

## Where to start

<div class="cards" markdown>

<div class="card" markdown>
### :material-school-outline:{ .card-icon } I want a literature review
Start with the **[Tutorial](tutorial.md)**: install, describe your review, and
read the results. Then see **[Example requests](requests.md)** and
**[Example results](examples.md)**.
</div>

<div class="card" markdown>
### :material-code-braces:{ .card-icon } I want to change the toolkit
Start with **[How it works](pipeline.md)**: the procedure the agent follows,
every script, and every check. Then see the
**[Tools reference](tools.md)** and **[Maintaining the docs](maintaining.md)**.
</div>

</div>

## What you get

Every review produces a spreadsheet and a timeline, and a written review if you
ask for one. These come from a real review of the creatine deficiency disorders
of the brain; click any of them to open it.

--8<-- "docs/_includes/what_you_get.md"

## What you decide

The agent does the searching and checking. You make three decisions, and it asks
you for each one:

1. **The scope.** What the review covers, how far back it goes, and how big it
   is.
2. **The families.** The agent proposes how to group the papers. You accept the
   groups, change them, or skip the timeline.
3. **The write-up.** Whether you want a written review.

Everything else has a right answer that a script can check: a DOI either points
to the cited paper or it does not. So scripts check it, and a failed check stops
the review until it is fixed.

## AI disclosure

**The toolkit was built with AI.** Most of its code and documentation were
written by Claude, Anthropic's AI model, under the direction of Jack Gallant
(Gallant Lab, UC Berkeley).

**What it produces is AI-generated too.** An AI agent runs the searches, writes
each paper's summary from its abstract (not the full text), proposes the
families, and writes the reviews. Every written review states its AI authorship.

**Only facts are checked by machine.** The scripts check every citation against
the literature databases and rebuild every reference from its DOI. Summaries,
groupings and interpretation cannot be checked that way. Read them as an AI's
reading of the abstracts.
