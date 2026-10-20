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

<p class="hero-meta">Version 2.4.10 · MIT license · <a href="#ai-disclosure">AI disclosure</a></p>

</div>

<figure class="fig hero-fig" markdown>
![A timeline of 190 papers on how the brain represents complexity, in six family lanes from 1948 to 2026](assets/figures/lineage_complexity.png)
<figcaption markdown>
**A finished timeline:** 190 checked papers in six families of ideas, 1948–2026.
</figcaption>
</figure>

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
ask for one. The pictures below are examples from one review, on the creatine
deficiency disorders of the brain. Yours will show your own topic and papers.

<div class="showcase" markdown>

<div class="showcase-card" markdown>
<span class="showcase-tag">Example</span>
![The first rows of a review's spreadsheet](assets/examples/creatine/spreadsheet_preview.png)

**:material-table-large: The spreadsheet**{ .showcase-title }
One row per paper: its full reference, a link to it, a one-sentence summary, its
family and its citation counts.
</div>

<div class="showcase-card" markdown>
<span class="showcase-tag">Example</span>
![A review's interactive timeline](assets/examples/creatine/timeline_preview.png)

**:material-chart-timeline-variant: The timeline**{ .showcase-title }
An interactive page that lays the papers out by family and year. Click any paper
to read its summary.
</div>

<div class="showcase-card" markdown>
<span class="showcase-tag">Example</span>
![The opening page of a written review](assets/examples/creatine/review_preview.png)

**:material-file-document-edit-outline: The written review**{ .showcase-title }
Optional. A narrative review drafted by the agent, citing only the checked
papers.
</div>

</div>

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
