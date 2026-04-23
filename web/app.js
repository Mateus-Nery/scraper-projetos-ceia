const state = {
  data: null,
  activeArea: "Todos",
  activeType: "Todos",
  search: "",
};

const heroStats = document.querySelector("#hero-stats");
const areaFilters = document.querySelector("#area-filters");
const typeFilters = document.querySelector("#type-filters");
const areaSummary = document.querySelector("#area-summary");
const typeSummary = document.querySelector("#type-summary");
const cardsGrid = document.querySelector("#cards-grid");
const emptyState = document.querySelector("#empty-state");
const resultsSummary = document.querySelector("#results-summary");
const typeCountLabel = document.querySelector("#type-count-label");
const areaCountLabel = document.querySelector("#area-count-label");
const summaryAreaTotal = document.querySelector("#summary-area-total");
const summaryTypeTotal = document.querySelector("#summary-type-total");
const clearFiltersButton = document.querySelector("#clear-filters");
const searchInput = document.querySelector("#search-input");
const dialog = document.querySelector("#project-dialog");
const dialogContent = document.querySelector("#dialog-content");

async function loadData() {
  const response = await fetch("./data/projects.json");
  if (!response.ok) {
    throw new Error("Não foi possível carregar o catálogo.");
  }
  state.data = await response.json();
  render();
}

function render() {
  renderHeroStats();
  renderFilterGroups();
  renderSummaryPanels();
  renderCards();
}

function renderHeroStats() {
  const projectCount = state.data.projectCount;
  const responsibleCount = new Set(state.data.projects.map((project) => project.responsible)).size;
  const areasCount = state.data.areaCounts.length;
  const typesCount = state.data.typeCounts.length;

  const stats = [
    ["Projetos", projectCount],
    ["Responsáveis", responsibleCount],
    ["Áreas", areasCount],
    ["Tipos", typesCount],
  ];

  heroStats.innerHTML = stats
    .map(
      ([label, value]) => `
        <article class="stat-card">
          <span class="stat-label">${label}</span>
          <strong>${value}</strong>
        </article>
      `,
    )
    .join("");
}

function renderFilterGroups() {
  const typeOptions = [{ label: "Todos", count: state.data.projectCount }, ...state.data.typeCounts];
  const areaOptions = [{ label: "Todos", count: state.data.projectCount }, ...state.data.areaCounts];

  typeCountLabel.textContent = `${state.data.typeCounts.length} categorias`;
  areaCountLabel.textContent = `${state.data.areaCounts.length} categorias`;

  typeFilters.innerHTML = buildChipGroup(typeOptions, state.activeType, "type");
  areaFilters.innerHTML = buildChipGroup(areaOptions, state.activeArea, "area");

  document.querySelectorAll("[data-filter-group]").forEach((button) => {
    button.addEventListener("click", () => {
      const group = button.dataset.filterGroup;
      const value = button.dataset.filterValue;
      if (group === "type") {
        state.activeType = value;
      } else {
        state.activeArea = value;
      }
      renderCards();
      renderFilterGroups();
    });
  });
}

function buildChipGroup(options, activeValue, group) {
  return options
    .map(
      ({ label, count }) => `
        <button
          type="button"
          class="chip ${label === activeValue ? "active" : ""}"
          data-filter-group="${group}"
          data-filter-value="${label}"
        >
          ${label} <span aria-hidden="true">·</span> ${count}
        </button>
      `,
    )
    .join("");
}

function renderSummaryPanels() {
  summaryAreaTotal.textContent = `${state.data.areaCounts.length} áreas`;
  summaryTypeTotal.textContent = `${state.data.typeCounts.length} tipos`;
  areaSummary.innerHTML = buildSummaryList(state.data.areaCounts);
  typeSummary.innerHTML = buildSummaryList(state.data.typeCounts);
}

function buildSummaryList(items) {
  const max = Math.max(...items.map((item) => item.count), 1);
  return items
    .map(
      (item) => `
        <div class="summary-item">
          <div class="summary-item-header">
            <strong>${item.label}</strong>
            <span>${item.count}</span>
          </div>
          <div class="summary-bar"><span style="width:${(item.count / max) * 100}%"></span></div>
        </div>
      `,
    )
    .join("");
}

function getFilteredProjects() {
  const query = state.search.trim().toLowerCase();
  return state.data.projects.filter((project) => {
    const matchArea = state.activeArea === "Todos" || project.area === state.activeArea;
    const matchType = state.activeType === "Todos" || project.type === state.activeType;
    const haystack = `${project.description} ${project.responsible}`.toLowerCase();
    const matchSearch = !query || haystack.includes(query);
    return matchArea && matchType && matchSearch;
  });
}

function renderCards() {
  const projects = getFilteredProjects();
  resultsSummary.textContent = `${projects.length} projetos visíveis`;
  cardsGrid.innerHTML = projects
    .map(
      (project) => `
        <article class="project-card" tabindex="0" data-project-id="${project.id}">
          <h2 class="project-description">${project.description}</h2>
          <div class="responsible-row">
            <div class="responsible-avatar" aria-hidden="true">${initials(project.responsible)}</div>
            <div>
              <p class="responsible-label">Responsável</p>
              <p class="responsible-name">${project.responsible}</p>
            </div>
          </div>
        </article>
      `,
    )
    .join("");

  emptyState.classList.toggle("hidden", projects.length !== 0);
  cardsGrid.classList.toggle("hidden", projects.length === 0);

  document.querySelectorAll("[data-project-id]").forEach((card) => {
    card.addEventListener("click", () => openProject(card.dataset.projectId));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        openProject(card.dataset.projectId);
      }
    });
  });
}

function openProject(id) {
  const project = state.data.projects.find((entry) => entry.id === id);
  if (!project) return;

  dialogContent.innerHTML = `
    <p class="eyebrow">Projeto CEIA</p>
    <h2 class="dialog-title">${project.description}</h2>
    <p class="summary-copy" style="margin-top: 12px;">
      Responsável: <strong>${project.responsible}</strong>
    </p>
    <div class="dialog-meta">
      ${dialogMetaCard("Área", project.area)}
      ${dialogMetaCard("Tipo", project.type)}
      ${dialogMetaCard("Modalidade original", project.modality || "Não informada")}
      ${dialogMetaCard("Instrumento", project.agreementType || "Não informado")}
      ${dialogMetaCard("Vigência", `${project.startDate || "?"} até ${project.endDate || "?"}`)}
      ${dialogMetaCard("Centro de custo", project.id || "Não informado")}
      ${dialogMetaCard("Código externo", project.controlCode || "Não informado")}
      ${dialogMetaCard("Instituição concedente", project.contractor || "Não informada")}
    </div>
  `;

  dialog.showModal();
}

function dialogMetaCard(label, value) {
  return `
    <div class="dialog-meta-card">
      <span>${label}</span>
      <strong>${value}</strong>
    </div>
  `;
}

function initials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

searchInput.addEventListener("input", (event) => {
  state.search = event.target.value;
  renderCards();
});

clearFiltersButton.addEventListener("click", () => {
  state.activeArea = "Todos";
  state.activeType = "Todos";
  state.search = "";
  searchInput.value = "";
  render();
});

loadData().catch((error) => {
  cardsGrid.innerHTML = `<div class="empty-state"><h2>Erro ao carregar</h2><p>${error.message}</p></div>`;
});
