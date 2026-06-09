import {elements} from "./dom.js";

let activeTrigger = null;
let closeTimer = 0;
const detailModalCloseDelay = 220;

function openDetailModal(templateId, trigger) {
	const template = document.querySelector(`#${templateId}`);
	if (!template || !elements.detailModal || !elements.detailModalContent || !elements.detailModalClose) {
		return;
	}

	window.clearTimeout(closeTimer);
	closeTimer = 0;
	activeTrigger = trigger;
	elements.detailModalContent.innerHTML = "";
	elements.detailModalContent.append(template.content.cloneNode(true));
	elements.detailModal.hidden = false;
	document.body.classList.add("detail-modal-open");
	elements.detailModal.getBoundingClientRect();
	elements.detailModal.classList.add("is-open");
	elements.detailModalClose.focus();
}

function closeDetailModal() {
	if (!elements.detailModal || !elements.detailModalContent || elements.detailModal.hidden || closeTimer) {
		return;
	}

	const trigger = activeTrigger;
	elements.detailModal.classList.remove("is-open");
	document.body.classList.remove("detail-modal-open");
	closeTimer = window.setTimeout(() => {
		closeTimer = 0;
		if (elements.detailModal.classList.contains("is-open")) {
			return;
		}

		elements.detailModal.hidden = true;
		elements.detailModalContent.innerHTML = "";
		trigger?.focus();
		if (activeTrigger === trigger) {
			activeTrigger = null;
		}
	}, detailModalCloseDelay);
}

export function initDetailModal() {
	const triggers = document.querySelectorAll("[data-detail-modal]");
	if (!elements.detailModal || !triggers.length) {
		return false;
	}

	triggers.forEach((trigger) => {
		trigger.addEventListener("click", () => openDetailModal(trigger.dataset.detailModal, trigger));
		trigger.addEventListener("keydown", (event) => {
			if (event.key === "Enter" || event.key === " ") {
				event.preventDefault();
				openDetailModal(trigger.dataset.detailModal, trigger);
			}
		});
	});

	elements.detailModalClose?.addEventListener("click", closeDetailModal);
	elements.detailModal.addEventListener("click", (event) => {
		if (event.target === elements.detailModal) {
			closeDetailModal();
		}
	});
	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape" && elements.detailModal && !elements.detailModal.hidden) {
			closeDetailModal();
		}
	});

	return true;
}
