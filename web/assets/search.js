const input = document.querySelector("#search-input");
const status = document.querySelector("#search-status");
const collections = document.querySelector("#collections");
const results = document.querySelector("#search-results");
const documents = window.qaSearchIndex.map((doc) => ({
  ...doc,
  label: `${doc.title} ${doc.group} ${doc.summary}`.toLowerCase(),
  textLower: doc.text.toLowerCase(),
}));

function matchedExcerpt(doc, terms) {
  const term = terms.find((value) => doc.textLower.includes(value));
  if (!term) return document.createTextNode(doc.summary);

  const position = doc.textLower.indexOf(term);
  const start = Math.max(0, position - 28);
  const end = Math.min(doc.text.length, position + term.length + 48);
  const excerpt = document.createDocumentFragment();
  const highlight = document.createElement("mark");
  highlight.textContent = doc.text.slice(position, position + term.length);
  excerpt.append(start ? "…" : "", doc.text.slice(start, position), highlight);
  excerpt.append(doc.text.slice(position + term.length, end), end < doc.text.length ? "…" : "");
  return excerpt;
}

function resultCard(doc, terms) {
  const item = document.createElement("li");
  const link = document.createElement("a");
  link.className = "document-card";
  link.href = doc.url;

  const group = document.createElement("span");
  group.className = "search-category";
  group.textContent = doc.group;
  const title = document.createElement("span");
  title.className = "card-title";
  title.textContent = doc.title;
  const snippet = document.createElement("span");
  snippet.className = "card-summary";
  snippet.append(matchedExcerpt(doc, terms));

  link.append(group, title, snippet);
  item.append(link);
  return item;
}

function search() {
  const query = input.value.trim().toLowerCase();
  const isSearching = query !== "";
  collections.hidden = isSearching;
  results.hidden = !isSearching;
  status.hidden = !isSearching;
  if (!isSearching) return;

  const terms = query.split(/\s+/u);
  const matches = documents.filter((doc) =>
    terms.every((term) => doc.label.includes(term) || doc.textLower.includes(term)),
  );
  const score = (doc) => terms.filter((term) => doc.label.includes(term)).length;
  matches.sort((first, second) => score(second) - score(first));
  results.querySelector("ul").replaceChildren(...matches.map((doc) => resultCard(doc, terms)));
  status.textContent = matches.length ? `找到 ${matches.length} 篇资料` : "没有找到匹配的资料";
}

document.querySelector("#search").hidden = false;
input.addEventListener("input", search);
document.querySelector(".top-nav").addEventListener("click", (event) => {
  if (event.target.closest("a")) {
    input.value = "";
    search();
  }
});
search();
