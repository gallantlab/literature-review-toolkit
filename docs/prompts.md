# Writing the request

The hardest part of a review is often the first message. This page shows
requests from real builds, what each one got right, and what the agent still had
to ask. The builds date from August to October 2026.

Every request in the examples is quoted as it was typed, typos and lowercase included: a request
does not need to be polished to work. The only edits are bracketed: a company
name, and one long reference shortened.

## What a good request contains

You do not need all of these. The agent asks about anything missing at the
Phase 1 checkpoint ([manual §4.1](manual.md#41-topic-mode)). But each one you
supply is a question it does not have to ask, and a guess it does not have to make.

| | Say | Why it helps |
|---|---|---|
| 1 | **What a paper must do to be in.** "Studies that compare X across Y", not just "X". | It becomes the inclusion test every search lane applies. |
| 2 | **The aspects you care about**, and that there are others. | Each named aspect tends to become a search lane. "There are certainly others" invites lanes you did not name. |
| 3 | **Where you think the literature lives**: fields, species, methods. | It tells the agent where to look first, and what counts as adjacent. |
| 4 | **What is out.** | Exclusions are written into every lane's brief, so they hold across the whole search. |
| 5 | **How far back**, and a recent landmark to reach. | The antecedents pass always runs, but a date sets its depth. A recent anchor ("the latest Neuropixels results") stops the search from ending a few years ago. |
| 6 | **Papers you already know**, however you remember them. | Verification checks them before they are used, so a wrong year or author does no harm. |
| 7 | **The size**, if it is not the default. | "A quick look", "the core literature", "everything" or "about 300 papers" each map to a scale ([manual §4.1](manual.md#41-topic-mode)). |
| 8 | **What you want at the end.** | The spreadsheet is always built and the timeline is always offered. Ask for anything beyond them: a written review, plots, a pro-and-con assessment. |

!!! tip "Say *only* when you mean only"
    "Papers that train networks on neural data" can be read as the method
    alone, or as the method plus its antecedents and close variants. If you want
    the method alone, say so. Otherwise the agent has to ask, or guess.

---

## Requests that name their dimensions

### Laminar differences in cortex

> do a new literature review of neurophysiology studies that have focused on
> differences across cortical layers. two important differences that people may
> have looked at are diffs in timing of communication, and differences in the
> representation of information. another is differences in spiking patterns or
> spiking characteristics. but there are certainly others. go back at least to
> the 1970s. include the most recent neuropixels results. organize the lanes and
> make the interactive html.

**Why it works.** The first sentence is an inclusion test: a study is in if the
cortical layer is the variable. The three named differences became three of the
aspects to cover, and "there are certainly others" let the agent add three more:
oscillations, circuit architecture, and how the laminar profile changes with
state, development and learning. The request sets both ends of the time span:
the 1970s and the most recent Neuropixels work. It also names the deliverable.

**What the agent still asked.** Whether laminar fMRI and MEG count (yes, as a
lane of their own). Whether slice physiology counts (yes, inside the circuit
lane). Which areas and species (all cortex, with V1 as the spine). And how big
(about 450–550 papers).

**Result.** 555 papers, 1909–2026, in six families.

### Linear and nonlinear summation

> run a new bibliography search. the focus should be on linear versus nonlinear
> summation in the neurophysiological responses of neurons. i suspect that much
> of the literature will come from vision studies. also include any such studies
> that used other brain measurements, such as fMRI or EEG. the oldest studies on
> this may be from the 1950s.

**Why it works.** It states where the bulk of the literature probably lives
(vision) and still widens the search to other measurements. A hunch about the
oldest studies sets the depth of the antecedents pass.

**What the agent still asked.** Which kinds of summation are in: receptive-field
summation, cross-modal and binocular combination, other senses. The answer took
dendritic integration out.

**Result.** 874 papers in six families. A later request, *"write the review
paper. be sure to follow gallant lab guidelines in ../WRITING/"*, produced a
written review citing 499 of them, written to the lab's style guide.

### The alignment problem in AI

> run another bibliography search on the "alignment" problem in AI. include
> theoretical/philosophical/opinion pieces on the problem, papers on how to
> measure it, and papers on how to fix it.

**Why it works.** Three kinds of work, named in one sentence: the problem, how to
measure it, and how to fix it. The agent covered them in equal measure. Naming
opinion pieces explicitly kept them in, although a search for empirical work
would have dropped them.

**Result.** 475 papers in seven families.

### Creatine deficiency

> do a new literature search on creatine transporter deficiancy. cover the history
> of research in the field. be sure to include cerebral creatine deficiencies
> (AGAT and GAMT). also cover the history and current state of treatments for
> these disorders. be sure to cover creatine MRS imaging as a diagnostic tool.

**Why it works.** It reads like a table of contents. Each sentence became a lane:
the main disorder, its two relatives, treatment, and the diagnostic method.

**A follow-up question.** *"i am particulary interested in any HUMAN anatomy
studies that look at physical anatomy (ultrastructure, synpases, neurons, etc) in
creatine disorders. are there any?"* Once the corpus exists, you can ask it
questions like this one.

**Result.** 587 papers in seven families. After approving the families, the user
asked for a written review, which cites 244 of them.

---

## Requests anchored on papers you know

### Networks fit end-to-end to neural data

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

**Why it works.** Three full references define the method more precisely than
any description could. "Very specific" and "BE SPECIFIC" kept the scope narrow:
networks whose weights are fit to recorded responses. It also says what *not*
to build, so the first pass was a quick search with no figure.

**How it grew.** The quick search found far more papers than expected, so the
user widened the request: *"please write a spreadsheet file like you usually do,
along with the other stuff that you usually save. and since there are a LOT more
papers than i thought, go ahead and do the taxonomy figure and whatever else you
usually do."* Starting small is fine.

**A scope correction mid-build.** *"at least some of the papers in your bib were
NOT TRAINED END TO END. for example, [Wang et al., 2025, Nature] AFAIK used a
pre-trained model."* That correction led to a check of every paper's methods,
and papers built on reused pretrained networks were marked separately. When a
result looks wrong, say so with an example.

**Result.** 168 papers in four families.

### Synthesizing stimuli to probe visual neurons

> i want a review on the use of generative models and/or genetic algorithms to
> understand how neurons or brain areas represent visual information. some
> relevant papers are:<br>
> ce connor current biology 2021 "Early Emergence of Solid Shape Coding in Natural and Deep Network Vision"<br>
> af luo neurips 2024 "Brain diffusion for visual exploration..."<br>
> but there are many other papers. i want to know what is the earliest paper that
> did this, and then do the evolution of the method.

**Why it works.** "The earliest paper that did this" makes the history the
point, so the antecedents pass searched pre-deep-learning closed-loop methods.
The two named papers fixed what "this" means, even with only initials and a
partial title. "There are many other papers" says the seeds are examples, not
the whole list.

**What verification caught.** The first paper is by Srinath et al., with Connor
as senior author. The second appeared at NeurIPS 2023, not 2024. Recall from
memory is fine in a request; verification corrects it.

**What the agent still asked.** How broad "generative" should be. The user chose
the broad reading: genetic algorithms, generative models and images optimized
through encoding models, but not decoding or reconstruction.

**Result.** 415 papers in five families.

---

## Requests that specify the output

### How accurate is diagnosis?

> i want to run a literature review specifically focused on the accuracy of
> diagnosis of brain disorders and mental disorders. i want to evaluate all
> classes of diagnosis: antomy, genetics, and behavior. in the end i want you to
> make TWO html plots, one where the rows are the disorders, and one where the
> rows are anatomy, genetics, and behavior. then based on that literature review,
> i want you to give me summary statitics about how accurate diagnosis is as of
> today. be SURE to cite all the relevant citations when you give me the summary,
> and to flag the most important papers that you used to create the summary.

**Why it works.** It describes the finished product, so the agent built the
pipeline backward from it. Plotting accuracy requires numbers, so the build
added a step that extracts accuracy figures from abstracts. A script checked
every extracted number against a verbatim quote.

**What the agent still asked.** Meta-analyses first or primary studies (meta-analyses,
plus landmark primary studies). How many disorders (about 20). Whether to add
physiology and biomarkers as a fourth kind of evidence (yes). Whether to include
machine-learning classifiers (no).

**A follow-up that split the project.** *"can you do an after-analysis that
summarizes this information just for fMRI? it would be helpful if you could break
the fMRI results into different approaches, like resting state, task-based,
etc."* Most fMRI results come from machine-learning classifiers, which the main
review had excluded, so the agent asked how to treat them. The answer: *"i'm fine
with 1, but the fMRI stuff needs to be broken out so that it can be evaluated
separately from the other studies."* That became a separate project, so nothing
in it changes the parent review's statistics.

**Result.** 745 papers, two plots and a summary page. The fMRI project added 582
papers.

### A therapy you are skeptical of

> do a literature search on microtesla magnetic therapy. personally i don't think
> that this could possibly do anything, i am very skeptical. give me the pro- and
> anti- sides.

A few minutes later:

> there is a company [name and website], figure out what field they use and
> target that.

**Why it works.** "The pro- and anti- sides" asks for an assessment, not a survey. The agent
searched both sides in equal measure and grouped papers by what they found.
Pointing at a real device let it pin the claim down from the company's patent:
the carrier frequency, the field strength and the dose. Papers using fields a
thousand times stronger could then be set aside.

**Result.** 668 papers in eight families, and a written review that gives the
case for, the case against and a verdict, citing 199 papers.

---

## Short requests

Short requests work. The agent writes down how it read the request in
`topic_definition.md`, and asks when the request is ambiguous.

> Do a literature review and find all the psychology and/or neuroscience studies
> on reverse Polish notation.

The agent read this at the widest defensible scope: any study in which postfix,
prefix or stack-based evaluation order is the object of study. That included
calculator human factors, programming notation and mathematics education. The
result was 177 papers. Seven of them are the entire experimental literature, and
they disagree.

> Do a literature review on how brain networks are affected by meditation.

The agent asked about methods and populations. The user chose the widest answer
on every axis: fMRI, EEG and MEG, structural and neurochemical work; experts and
novices, clinical interventions, development and aging. The result was 396
papers in six families.

---

## Requests after the first build

Most builds take a few more messages. These are typical.

| You want | Say something like |
|---|---|
| The families as proposed | *"the timeline families are fine, do it"* |
| A written review | *"write the review paper. be sure to follow gallant lab guidelines in ../WRITING/"* |
| A review that argues a question | *"write the review paper. at the end of the review answer the following question in debate format, including a pro position, an anti position, and a conclusion: "layers are functionally important". support your debate points with citations from the bibliography."* |
| A question about the corpus | *"i am particulary interested in any HUMAN anatomy studies ... are there any?"* |
| A separate analysis of one part | *"can you do an after-analysis that summarizes this information just for fMRI?"* |
| A rerun with the current toolkit | *"rerun the gallantlab search w/the new codebase"* ([manual §8.1](manual.md#81-upgrading-an-old-corpus)) |
| More papers on one subtopic | *"extend the existing review with another 20 papers on cerebello-thalamic projections"* |
| A change to the figure | *"show the family's claim when I hover over a lane"* |
