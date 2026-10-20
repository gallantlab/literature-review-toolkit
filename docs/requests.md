# Example requests

These are real requests from finished reviews, quoted as they were typed, typos
and all. A request does not need to be polished to work. The only edits are in
square brackets.

Each example has the same parts:

- **Request**: what the user typed.
- **Why it works**: what in the request shaped the review.
- **What the agent asked**: the questions the request left open.
- **Follow-ups**: later messages in the same conversation.
- **Result**: what the review produced.

For what to put in your own request, see
[Step 3 of the tutorial](tutorial.md#step-3-describe-the-review).

---

## Requests that name what matters

### Differences across cortical layers

**Request.**

> do a new literature review of neurophysiology studies that have focused on
> differences across cortical layers. two important differences that people may
> have looked at are diffs in timing of communication, and differences in the
> representation of information. another is differences in spiking patterns or
> spiking characteristics. but there are certainly others. go back at least to
> the 1970s. include the most recent neuropixels results. organize the lanes and
> make the interactive html.

**Why it works.** The first sentence says what a paper must do to be included:
treat the cortical layer as the thing being compared. The three named
differences each became a search. "There are certainly others" let the agent add
three more: brain rhythms, circuit wiring, and how layers change with state and
learning. The request sets both ends of the time span, the 1970s and the latest
Neuropixels recordings.

**What the agent asked.** Whether layer-resolved fMRI and MEG count (yes, as
their own search). Whether brain-slice studies count (yes). Which brain areas
(all of cortex, centered on primary visual cortex). How many papers (about
450–550).

**Follow-ups.** *"write the review paper. at the end of the review answer the
following question in debate format, including a pro position, an anti
position, and a conclusion: "layers are functionally important". support your
debate points with citations from the bibliography."*

**Result.** 555 papers from 1909 to 2026, in six families, and a written review
that ends in a debate. The [timeline](examples.md#differences-across-cortical-layers)
is on the Example results page.

### Linear and nonlinear summation

**Request.**

> run a new bibliography search. the focus should be on linear versus nonlinear
> summation in the neurophysiological responses of neurons. i suspect that much
> of the literature will come from vision studies. also include any such studies
> that used other brain measurements, such as fMRI or EEG. the oldest studies on
> this may be from the 1950s.

**Why it works.** It says where most papers probably are (vision), and still
widens the search to other measurements. A guess about the oldest studies tells
the agent how far back to search for the field's roots.

**What the agent asked.** Which kinds of summation count. Receptive-field
summation, combining the two eyes or two senses, and other senses were in.
Summation within single dendrites was out.

**Follow-ups.** *"write the review paper. be sure to follow gallant lab
guidelines in ../WRITING/"*. Pointing to a style guide made the written review
follow the lab's writing rules.

**Result.** 874 papers in six families, and a written review citing 499 of them.

### The alignment problem in AI

**Request.**

> run another bibliography search on the "alignment" problem in AI. include
> theoretical/philosophical/opinion pieces on the problem, papers on how to
> measure it, and papers on how to fix it.

**Why it works.** It names three kinds of work in one sentence: the problem, how
to measure it and how to fix it. The agent covered all three equally. Naming
opinion pieces kept them in; a search for experiments alone would have dropped
them.

**Follow-ups.** *"the timeline families are fine, do it."*

**Result.** 475 papers in seven families.

### Creatine deficiency

**Request.**

> do a new literature search on creatine transporter deficiancy. cover the history
> of research in the field. be sure to include cerebral creatine deficiencies
> (AGAT and GAMT). also cover the history and current state of treatments for
> these disorders. be sure to cover creatine MRS imaging as a diagnostic tool.

**Why it works.** It reads like a table of contents. Each sentence became a
search: the main disorder, its two relatives, treatment, and the imaging method
used to diagnose it.

**Follow-ups.** A request for a written review, and a question about the
papers: *"i am particulary interested in any HUMAN anatomy studies that look at
physical anatomy (ultrastructure, synpases, neurons, etc) in creatine disorders.
are there any?"*

**Result.** 587 papers from 1886 to 2026, in seven families, and a written review
citing 244 of them. The [timeline](examples.md#creatine-deficiency) is on the
Example results page.

---

## Requests built on papers you know

### Networks trained end-to-end on neural data

**Request.**

> run a quick, very specific search for papers that train neural networks
> end-to-end to model neurophysiological data from humans or animals. as far as i
> know the only papers that do this are (1) "Lau, B., Stanley, G. B., & Dan, Y.
> (2002). Computational subunits of visual cortical neurons revealed by artificial
> neural networks. Proceedings of the National Academy of Sciences, 99(13),
> 8974-8979.", (2) "Prenger, R., Wu, M. C. K., David, S. V., & Gallant, J. L.
> (2004). Nonlinear V1 responses to natural scenes revealed by neural network
> analysis. Neural Networks, 17(5-6), 663-679." and (3) "Oliver, M., Winter, M.,
> Dupré la Tour, T., Eickenberg, M., & Gallant, J. L. (2024). A
> biologically-inspired hierarchical convolutional energy model predicts V4
> responses to natural videos. bioRxiv, 2024-12." i want to know if there are any
> other papers out there. i do NOT need the taxonomy / timeline figure or a
> summary paper, i just need references. BE SPECIFIC.

**Why it works.** Three full references define the method more precisely than any
description could. "Very specific" kept the search narrow: networks whose weights
are fit to recorded brain responses. Saying what was *not* needed kept the first
pass to a quick list.

**Follow-ups.** The quick search found far more papers than expected, so the user
asked for the full review: *"please write a spreadsheet file like you usually do,
along with the other stuff that you usually save. and since there are a LOT more
papers than i thought, go ahead and do the taxonomy figure and whatever else you
usually do."* Later the user spotted an error: *"at least some of the papers in
your bib were NOT TRAINED END TO END. for example, [Wang et al., 2025, Nature]
AFAIK used a pre-trained model."* The agent then checked every paper's methods
and marked the ones built on pretrained networks. Starting small is fine, and so
is correcting course with one example.

**Result.** 168 papers in four families.

### Synthesizing images to probe visual neurons

**Request.**

> i want a review on the use of generative models and/or genetic algorithms to
> understand how neurons or brain areas represent visual information. some
> relevant papers are:<br>
> ce connor current biology 2021 "Early Emergence of Solid Shape Coding in Natural and Deep Network Vision"<br>
> af luo neurips 2024 "Brain diffusion for visual exploration..."<br>
> but there are many other papers. i want to know what is the earliest paper that
> did this, and then do the evolution of the method.

**Why it works.** Asking for "the earliest paper that did this" makes the history
the point, so the agent searched methods from before deep learning. Two papers,
remembered only by initials and part of a title, fixed what "this" means. "There
are many other papers" says they are examples, not the whole list.

**What the agent asked.** How broad "generative" should be. The user chose the
broad reading, which excludes decoding images from brain activity.

**Result.** 415 papers in five families. Checking corrected both remembered
papers: the first is by Srinath et al., with Connor as senior author, and the
second appeared at NeurIPS in 2023, not 2024. Details from memory are fine in a
request.

---

## Requests that describe the output

### How accurate is diagnosis?

**Request.**

> i want to run a literature review specifically focused on the accuracy of
> diagnosis of brain disorders and mental disorders. i want to evaluate all
> classes of diagnosis: antomy, genetics, and behavior. in the end i want you to
> make TWO html plots, one where the rows are the disorders, and one where the
> rows are anatomy, genetics, and behavior. then based on that literature review,
> i want you to give me summary statitics about how accurate diagnosis is as of
> today. be SURE to cite all the relevant citations when you give me the summary,
> and to flag the most important papers that you used to create the summary.

**Why it works.** It describes the finished product, so the agent planned
backward from it. Plotting accuracy needs numbers, so the agent added a step that
copies each accuracy figure from a paper's abstract, with a word-for-word quote
that a script then checks.

**What the agent asked.** Whether to favor summaries of many studies or single
studies (summaries, plus landmark single studies). How many disorders (about 20).
Whether to add a fourth kind of evidence, brain physiology and blood tests (yes).
Whether to include machine-learning classifiers (no).

**Follow-ups.** *"can you do an after-analysis that summarizes this information
just for fMRI? it would be helpful if you could break the fMRI results into
different approaches, like resting state, task-based, etc."* Most fMRI results
come from machine-learning classifiers, which the first review had left out, so
the agent asked how to treat them: *"i'm fine with 1, but the fMRI stuff needs to
be broken out so that it can be evaluated separately from the other studies."*
The fMRI analysis became a separate review, so it does not change the first
review's numbers.

**Result.** 745 papers, two plots and a summary page with its sources. The fMRI
review added 582 papers.

### A therapy you doubt

**Request.**

> do a literature search on microtesla magnetic therapy. personally i don't think
> that this could possibly do anything, i am very skeptical. give me the pro- and
> anti- sides.

A few minutes later:

> there is a company [name and website], figure out what field they use and
> target that.

**Why it works.** "The pro- and anti- sides" asks for an assessment, not a survey,
so the agent searched both sides equally and grouped papers by what they found.
Pointing at a real device let the agent pin down the claim from the company's
patent: the frequency, the field strength and the dose. Studies of fields a
thousand times stronger could then be set aside.

**Result.** 668 papers in eight families, and a written review that gives the
case for, the case against and a verdict, citing 199 papers.

---

## Short requests

Short requests work too. The agent writes down how it read the request, and asks
when something is unclear.

### Reverse Polish notation

**Request.**

> Do a literature review and find all the psychology and/or neuroscience studies
> on reverse Polish notation.

**Why it works.** "Find all" told the agent to take the widest reasonable
reading: any study of how people read, learn or use notation written in
operator-last or stack order. That took in calculator design, programming and
mathematics teaching.

**Result.** 177 papers. Only seven are experiments comparing notations, and they
disagree.

### Meditation and brain networks

**Request.**

> Do a literature review on how brain networks are affected by meditation.

**What the agent asked.** Which methods and which people. The user chose the
widest answer each time: fMRI, EEG, MEG, brain structure and brain chemistry;
experienced meditators and beginners, patients, children and older adults.

**Result.** 396 papers in six families.
