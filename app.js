const exhibitions = [
    {
        title: "Exposition test",
        venue: "Musée du Louvre",
        start: "2026-06-01",
        end: "2026-12-15"
    },
    {
        title: "Autre exposition",
        venue: "Musée d'Orsay",
        start: "2026-09-10",
        end: "2027-01-20"
    },
    {
        title: "Exposition à venir",
        venue: "Jeu de Paume",
        start: "2026-10-20",
        end: "2027-01-15"
    }
];

const today = new Date();

function renderExhibitions(type) {
    const container = document.getElementById("exhibitions");

    let filtered;

    if (type === "current") {
        filtered = exhibitions.filter(exhibition => {
            const start = new Date(exhibition.start);
            const end = new Date(exhibition.end);

            return start <= today && today <= end;
        });
    } else {
        const limit = new Date(today);
        limit.setDate(limit.getDate() + 30);

        filtered = exhibitions.filter(exhibition => {
            const start = new Date(exhibition.start);

            return start > today && start <= limit;
        });
    }

    filtered.sort((a, b) => {
        const dateA = new Date(type === "current" ? a.end : a.start);
        const dateB = new Date(type === "current" ? b.end : b.start);

        return dateA - dateB;
    });

    container.innerHTML = filtered.map(exhibition => `
        <article class="exhibition">
            <div class="exhibition-title">${exhibition.title}</div>
            <div class="exhibition-venue">${exhibition.venue}</div>
            <div class="exhibition-dates">
                ${formatDate(exhibition.start)} → ${formatDate(exhibition.end)}
            </div>
        </article>
    `).join("");
}

function formatDate(date) {
    return new Date(date).toLocaleDateString("fr-FR", {
        day: "numeric",
        month: "long",
        year: "numeric"
    });
}

document.querySelectorAll(".tab").forEach(button => {
    button.addEventListener("click", () => {
        document.querySelectorAll(".tab").forEach(tab => {
            tab.classList.remove("active");
        });

        button.classList.add("active");

        renderExhibitions(button.dataset.tab);
    });
});

renderExhibitions("current");
