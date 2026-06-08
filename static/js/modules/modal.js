import {elements} from "./dom.js";

let activeTrigger = null;
let closeTimer = null;

function settleOpenAnimation() {
	if (!elements.backdrop) {
		return;
	}

	elements.backdrop.classList.remove("is-opening");
	elements.backdrop.classList.add("is-open");
}

function openModal(templateId, trigger) {
	const template = document.querySelector(`#${templateId}`);
	if (!template || !elements.backdrop || !elements.modalContent) {
		return;
	}

	window.clearTimeout(closeTimer);
	activeTrigger = trigger;
	elements.modalContent.innerHTML = "";
	elements.modalContent.append(template.content.cloneNode(true));
	elements.backdrop.classList.remove("is-open", "is-closing");
	elements.backdrop.classList.add("is-opening");
	elements.backdrop.hidden = false;
	document.body.classList.add("modal-open");
	requestAnimationFrame(settleOpenAnimation);
	elements.closeButton?.focus();
}

function closeModal() {
	if (!elements.backdrop || !elements.modalContent) {
		return;
	}

	if (elements.backdrop.hidden || elements.backdrop.classList.contains("is-closing")) {
		return;
	}

	elements.backdrop.classList.remove("is-opening", "is-open");
	elements.backdrop.classList.add("is-closing");
	document.body.classList.remove("modal-open");
	closeTimer = window.setTimeout(() => {
		elements.backdrop.hidden = true;
		elements.backdrop.classList.remove("is-closing");
		elements.modalContent.innerHTML = "";
		activeTrigger?.focus();
		activeTrigger = null;
	}, 180);
}

export function initModals() {
	document.querySelectorAll("[data-modal-target]").forEach((trigger) => {
		trigger.addEventListener("click", () => openModal(trigger.dataset.modalTarget, trigger));
		trigger.addEventListener("keydown", (event) => {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				openModal(trigger.dataset.modalTarget, trigger);
			}
		});
	});

	elements.closeButton?.addEventListener("click", closeModal);
	elements.backdrop?.addEventListener("click", (event) => {
		if (event.target === elements.backdrop) {
			closeModal();
		}
	});

	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape" && elements.backdrop && !elements.backdrop.hidden) {
			closeModal();
		}
	});
}

