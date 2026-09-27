let exhibitions = [];

const today = new Date();
today.setHours(0, 0, 0, 0);

async function loadExhibitions() {
    try {
        const response = await fetch("data/exhibitions.json");

        if (!response.ok) {
            throw new Error("Impossible de charger les données");
        }

        exhibitions = await response.json();

        renderExhibitions("current");

    } catch (error) {
        console.error(error);

        document.getElementById("exhibitions").innerHTML = `
            <p>
                Impossible de charger les expositions pour le moment.
            </p>
        `;
    }
}

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

    if (filtered.length === 0) {
        container.innerHTML = `
            <p>Aucune exposition.</p>
        `;
        return;
    }

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

loadExhibitions();
