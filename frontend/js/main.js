let currentDocumentId = null;
let token = null;
let currentCategory = null;
let documents = [];
let currentDocumentIndex = -1;
// Zoom feature
let currentScale = 1;
let currentX = 0;
let currentY = 0;
let isDragging = false;
let startX = 0;
let startY = 0;

const API_URL = "http://localhost:8000";

// Authentication
async function login(username, password) {
	const response = await fetch(`${API_URL}/reviewer-token`, {
		method: "POST",
		headers: {
			"Content-Type": "application/x-www-form-urlencoded",
		},
		body: `username=${encodeURIComponent(
			username
		)}&password=${encodeURIComponent(password)}`,
	});

	if (!response.ok) {
		const error = await response.text();
		throw new Error(error);
	}

	const data = await response.json();
	token = data.access_token;
	localStorage.setItem("token", token);
	return token;
}

// API calls
async function fetchCategories() {
	const response = await fetch(`${API_URL}/categories/`, {
		headers: {
			Authorization: `Bearer ${token}`,
		},
	});
	return await response.json();
}

async function fetchDocuments(categoryId, reviewed = false) {
	const response = await fetch(
		`${API_URL}/documents/${categoryId}?reviewed=${reviewed}`,
		{
			headers: {
				Authorization: `Bearer ${token}`,
			},
		}
	);
	return await response.json();
}

async function fetchEntries(documentId) {
	const response = await fetch(`${API_URL}/document/${documentId}/entries`, {
		headers: {
			Authorization: `Bearer ${token}`,
		},
	});
	return await response.json();
}

// document loading functions
async function loadDocuments(categoryId, reviewed = false) {
	try {
		documents = await fetchDocuments(categoryId, reviewed);
		currentDocumentIndex = documents.length > 0 ? 0 : -1;

		// Update document counts
		await updateDocumentCounts(categoryId);

		if (currentDocumentIndex >= 0) {
			await showDocument(documents[currentDocumentIndex].id);
		} else {
			document.getElementById("review-container").classList.add("hidden");
			document.getElementById("entries-list").innerHTML = "";
		}
	} catch (error) {
		console.error("Error loading documents:", error);
		alert("Error loading documents");
	}
}

async function showDocument(documentId) {
	try {
		currentDocumentId = documentId;
		const currentDoc = documents.find((d) => d.id === documentId);

		if (!currentDoc) {
			throw new Error("Document not found");
		}

		// Clear the entries list
		const entriesList = document.getElementById("entries-list");
		entriesList.innerHTML = "";

		// Display entries
		currentDoc.entries.forEach((entry) => {
			const div = document.createElement("div");
			div.className = "entry-item";
			const safeValue = entry.field_value || ""; // Handle null/undefined values
			div.innerHTML = `
                <label>${entry.field_name}</label>
                <input
                    type="text"
                    value="${safeValue}"
                    data-original-value="${safeValue}"
                    data-field-name="${entry.field_name}"
                >
            `;
			entriesList.appendChild(div);
		});

		// Update image
		const imageElement = document.getElementById("document-image");
		imageElement.src = currentDoc.image_url;

		// Show review container
		document.getElementById("review-container").classList.remove("hidden");
		updateNavigationAfterReview();
	} catch (error) {
		console.error("Error showing document:", error);
		alert("Error loading document");
	}
}

async function updateFields(documentId, updates) {
	try {
		const response = await fetch(
			`${API_URL}/review/document/${documentId}/update`,
			{
				method: "PUT",
				headers: {
					Authorization: `Bearer ${token}`,
					"Content-Type": "application/json",
				},
				body: JSON.stringify(updates),
			}
		);

		if (!response.ok) {
			throw new Error("Failed to update fields");
		}

		return await response.json();
	} catch (error) {
		console.error("Error updating fields:", error);
		throw error;
	}
}

// Wheel zoom support
document
	.getElementById("image-container-inner")
	.addEventListener("wheel", (e) => {
		e.preventDefault();
		const delta = Math.sign(e.deltaY);
		const zoomFactor = 0.1;

		if (delta < 0) {
			currentScale = Math.min(currentScale * (1 + zoomFactor), 5);
		} else {
			currentScale = Math.max(currentScale * (1 - zoomFactor), 0.5);
		}

		updateTransform();
	});

// Event Listeners
document.getElementById("login-form").addEventListener("submit", async (e) => {
	e.preventDefault();
	const username = document.getElementById("username").value;
	const password = document.getElementById("password").value;

	try {
		await login(username, password);
		document.getElementById("login-container").classList.add("hidden");
		document.getElementById("main-container").classList.remove("hidden");
		loadCategories();
	} catch (error) {
		alert("Login failed");
	}
});

document
	.getElementById("category-select")
	.addEventListener("change", async (e) => {
		const categoryId = e.target.value;

		if (!categoryId) {
			console.error("No category selected");
			return;
		}

		console.log(`Selected Category ID: ${categoryId}`); // Debugging log
		currentCategory = categoryId;
		await loadDocuments(categoryId);
	});

document.getElementById("prev-btn").addEventListener("click", () => {
	if (currentDocumentIndex > 0) {
		currentDocumentIndex--;
		showDocument(documents[currentDocumentIndex].id);
	}
});

document.getElementById("next-btn").addEventListener("click", () => {
	if (currentDocumentIndex < documents.length - 1) {
		currentDocumentIndex++;
		showDocument(documents[currentDocumentIndex].id);
	}
});

document.getElementById("save-btn").addEventListener("click", async () => {
	try {
		const inputs = document.querySelectorAll("#entries-list input");
		const updates = {};
		let hasChanges = false;

		inputs.forEach((input) => {
			const fieldName = input.previousElementSibling.textContent;
			const currentValue = input.value;
			const originalValue = input.getAttribute("data-original-value");

			if (currentValue !== originalValue) {
				updates[fieldName] = currentValue;
				hasChanges = true;
			}
		});

		if (!hasChanges) {
			alert("No changes detected.");
			return;
		}

		// Send all updates in a single request
		const result = await updateFields(currentDocumentId, updates);

		// Update document counts
		await updateDocumentCounts(currentCategory);

		// Reload documents in current tab
		const isReviewedTab =
			document.querySelector(".tab-btn.active").dataset.status ===
			"reviewed";
		await loadDocuments(currentCategory, isReviewedTab);

		// alert("All changes saved successfully!");
	} catch (error) {
		console.error("Error saving changes:", error);
		alert("Error saving changes. Please try again.");
	}
});

document.getElementById("logout-btn").addEventListener("click", () => {
	localStorage.removeItem("token");
	token = null;
	document.getElementById("main-container").classList.add("hidden");
	document.getElementById("login-container").classList.remove("hidden");
	document.getElementById("login-form").reset();
});

// Add tab functionality
document.querySelectorAll(".tab-btn").forEach((button) => {
	button.addEventListener("click", async (e) => {
		document
			.querySelectorAll(".tab-btn")
			.forEach((btn) => btn.classList.remove("active"));
		button.classList.add("active");

		const reviewed = button.dataset.status === "reviewed";
		const categoryId = document.getElementById("category-select").value;

		// Show/hide download button based on reviewed status
		document
			.getElementById("download-btn")
			.classList.toggle("hidden", !reviewed);

		if (categoryId) {
			currentDocumentIndex = -1;
			await loadDocuments(categoryId, reviewed);
		}
	});
});

// Initialize
async function loadCategories() {
	const categories = await fetchCategories();
	const select = document.getElementById("category-select");
	select.innerHTML = '<option value="">Select a category</option>';
	categories.forEach((category) => {
		const option = document.createElement("option");
		// Use category.name because your backend only returns a "name" key
		option.value = category.name;
		option.textContent = category.name;
		select.appendChild(option);
	});
}

// Check for existing token on page load
window.addEventListener("load", () => {
	const savedToken = localStorage.getItem("token");
	if (savedToken) {
		token = savedToken;
		document.getElementById("login-container").classList.add("hidden");
		document.getElementById("main-container").classList.remove("hidden");
		loadCategories();
	}
});

// Update category change handler
document
	.getElementById("category-select")
	.addEventListener("change", async (e) => {
		const categoryId = e.target.value;
		if (categoryId) {
			try {
				const documents = await fetchDocuments(categoryId);
				if (documents && documents.length > 0) {
					const category =
						document.getElementById("category-select")
							.selectedOptions[0].text;
					showDocument(documents[0].id, category);
				} else {
					document
						.getElementById("review-container")
						.classList.add("hidden");
					// alert("No documents found in this category");
				}
			} catch (error) {
				console.error("Error fetching documents:", error);
				alert("Error loading documents");
			}
		}
	});

// Zoom feature
// function to update transform
function updateTransform() {
	const container = document.getElementById("image-container-inner");
	container.style.transform = `translate(${currentX}px, ${currentY}px) scale(${currentScale})`;
}

// Zoom and pan control event listeners
document.addEventListener("DOMContentLoaded", () => {
	// Zoom controls
	document.getElementById("zoom-in").addEventListener("click", () => {
		currentScale = Math.min(currentScale * 1.2, 5);
		updateTransform();
	});

	document.getElementById("zoom-out").addEventListener("click", () => {
		currentScale = Math.max(currentScale / 1.2, 0.5);
		updateTransform();
	});

	document.getElementById("reset-zoom").addEventListener("click", () => {
		currentScale = 1;
		currentX = 0;
		currentY = 0;
		updateTransform();
	});

	// Pan controls
	document.getElementById("pan-left").addEventListener("click", () => {
		currentX -= 50;
		updateTransform();
	});

	document.getElementById("pan-right").addEventListener("click", () => {
		currentX += 50;
		updateTransform();
	});

	document.getElementById("pan-up").addEventListener("click", () => {
		currentY -= 50;
		updateTransform();
	});

	document.getElementById("pan-down").addEventListener("click", () => {
		currentY += 50;
		updateTransform();
	});

	// Mouse drag pan
	const container = document.getElementById("image-container-inner");

	container.addEventListener("mousedown", (e) => {
		isDragging = true;
		startX = e.clientX - currentX;
		startY = e.clientY - currentY;
		container.style.cursor = "grabbing";
	});

	document.addEventListener("mousemove", (e) => {
		if (isDragging) {
			currentX = e.clientX - startX;
			currentY = e.clientY - startY;
			updateTransform();
		}
	});

	document.addEventListener("mouseup", () => {
		isDragging = false;
		container.style.cursor = "move";
	});
});

// Function to fetch counts for both sections
async function updateDocumentCounts(categoryId) {
	try {
		const allDocuments = await fetchDocuments(categoryId, false); // Unreviewed
		const reviewedDocuments = await fetchDocuments(categoryId, true); // Reviewed

		document.getElementById("unreviewed-count").textContent =
			allDocuments.length;
		document.getElementById("reviewed-count").textContent =
			reviewedDocuments.length;
	} catch (error) {
		console.error("Error updating counts:", error);
	}
}

// Function to handle navigation after document review
function updateNavigationAfterReview() {
	if (documents.length === 0) {
		document.getElementById("next-btn").disabled = true;
		document.getElementById("prev-btn").disabled = true;
	} else {
		document.getElementById("next-btn").disabled =
			currentDocumentIndex >= documents.length - 1;
		document.getElementById("prev-btn").disabled =
			currentDocumentIndex <= 0;
	}
}

// Download functionality
async function downloadCategoryData(categoryId) {
	try {
		const response = await fetch(
			`${API_URL}/download-category/${categoryId}`,
			{
				headers: {
					Authorization: `Bearer ${token}`,
				},
			}
		);

		if (!response.ok) {
			const error = await response.json();
			throw new Error(error.detail || "Download failed");
		}

		const blob = await response.blob();
		const url = window.URL.createObjectURL(blob);
		const a = document.createElement("a");
		a.href = url;

		// Generate filename with timestamp
		const category =
			document.getElementById("category-select").selectedOptions[0].text;
		const timestamp = new Date().toISOString().replace(/[:.]/g, "-");
		a.download = `${category}_reviewed_${timestamp}.zip`;

		document.body.appendChild(a);
		a.click();
		window.URL.revokeObjectURL(url);
		document.body.removeChild(a);
	} catch (error) {
		alert(error.message);
	}
}

// Add event listener for download button
document.getElementById("download-btn").addEventListener("click", () => {
	const categoryId = document.getElementById("category-select").value;
	if (categoryId) {
		downloadCategoryData(categoryId);
	}
});
