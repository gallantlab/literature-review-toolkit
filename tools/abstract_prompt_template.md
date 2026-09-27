# Missing-abstract brief — TEMPLATE (Phase 5c)

Do not fill this by hand. `tools/abstracts.py --rows rows.json --prepare-missing DIR`
renders it into DIR/BRIEF.md and writes DIR/need_NN.json with every row that has a
summary but no abstract from any API. Everything above the `BRIEF STARTS` marker is
these notes and is never sent. `abstracts.py --ingest-missing 'DIR/result_*.json'`
reads the answers back.

<!-- BRIEF STARTS -->
# Collect verbatim abstracts from landing pages

Each item in `{INPUT_DIR}/need_NN.json` (the NN you were given) is a paper in an
annotated bibliography for which no API (arXiv, OpenAlex, Semantic Scholar, PubMed,
Europe PMC) returned an abstract. Summaries in the bibliography are later checked
against these abstracts, so the text must be the paper's OWN abstract, copied
verbatim: never a summary, a review's description, or text you write.

For each item, try in order until one works (keep commands short, with timeouts):

1. PubMed: `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term=<doi>[doi]&retmode=json`
   (with curl, pass `-g` so the brackets are not read as a glob), then
   `efetch.fcgi?db=pubmed&id=<pmid>&rettype=abstract&retmode=xml` (read AbstractText).
   If the DOI search finds nothing, search by exact title.
2. Europe PMC: `https://www.ebi.ac.uk/europepmc/webservices/rest/search?query=DOI:<doi>&resultType=core&format=json`.
3. The DOI landing page or publisher page (`https://doi.org/<doi>`), or the arXiv or
   bioRxiv abstract page.
4. For a book or chapter: the publisher's own description of this exact work counts;
   record it with `"kind": "publisher-description"`.

Confirm the page is the right paper (title and first author match the item) before
copying. The opening of the paper's body is NOT an abstract: a paper without one
(many commentaries and mini-reviews) gets `none`.

Write `{INPUT_DIR}/result_NN.json` (same NN), a JSON object keyed by ref, one entry
per input item:

- found: `{"text": "<verbatim abstract>", "url": "<the page you copied it from>",
  "doi": "<the item's doi, exactly as given>", "arxiv": "<the item's arxiv, exactly as given>",
  "kind": "abstract" | "publisher-description"}`
- none exists anywhere: `{"none": true, "checked": ["<url>", "..."]}`

Copy `doi` and `arxiv` from the input item unchanged: they bind the entry to its row.
Strip HTML tags and section labels like "Abstract", but keep the words verbatim.
Write the file incrementally and parse it back with python3. Never read or write
outside `{PROJECT_DIR}` except web fetches. Do NOT delegate to subagents.

Reply with only: found N, none N.
