import {elements} from "./dom.js";

let activeTrigger = null;
let closeTimer = 0;
const lifeToneClasses = ["life-tone-good", "life-tone-warning", "life-tone-danger", "life-tone-neutral"];
const modalCloseDelay = 220;

function setModalContent(trigger) {
	if (!elements.lifeModalLabel || !elements.lifeModalTitle || !elements.lifeModalText) {
		return;
	}

	elements.lifeModalLabel.textContent = trigger.dataset.lifeLabel || "生活指数";
	elements.lifeModalTitle.textContent = trigger.dataset.lifeDesc || "暂无";
	elements.lifeModalText.textContent = trigger.dataset.lifeText || "暂无内容";
	if (elements.lifeModalIcon) {
		elements.lifeModalIcon.className = `weather-icon ${trigger.dataset.lifeIcon || "i-leaf"}`;
	}
	if (elements.lifeModal) {
		elements.lifeModal.classList.remove(...lifeToneClasses);
		elements.lifeModal.classList.add(`life-tone-${trigger.dataset.lifeTone || "neutral"}`);
	}
}

function closeLifeModal() {
	if (!elements.lifeModal || elements.lifeModal.hidden || closeTimer) {
		return;
	}

	const trigger = activeTrigger;
	elements.lifeModal.classList.remove("is-open");
	document.body.classList.remove("life-modal-open");
	closeTimer = window.setTimeout(() => {
		closeTimer = 0;
		if (elements.lifeModal.classList.contains("is-open")) {
			return;
		}

		elements.lifeModal.hidden = true;
		elements.lifeModal.classList.remove(...lifeToneClasses);
		trigger?.focus();
		if (activeTrigger === trigger) {
			activeTrigger = null;
		}
	}, modalCloseDelay);
}

function openLifeModal(trigger) {
	if (!elements.lifeModal || !elements.lifeModalClose) {
		return;
	}

	window.clearTimeout(closeTimer);
	closeTimer = 0;
	activeTrigger = trigger;
	setModalContent(trigger);
	elements.lifeModal.hidden = false;
	document.body.classList.add("life-modal-open");
	elements.lifeModal.getBoundingClientRect();
	elements.lifeModal.classList.add("is-open");
	elements.lifeModalClose.focus();
}

export function initLifeModal() {
	const triggers = document.querySelectorAll(".life-card[data-life-label]");
	if (!elements.lifeModal || !triggers.length) {
		return false;
	}

	triggers.forEach((trigger) => {
		trigger.addEventListener("click", () => openLifeModal(trigger));
	});

	elements.lifeModalClose?.addEventListener("click", closeLifeModal);
	elements.lifeModal.addEventListener("click", (event) => {
		if (event.target === elements.lifeModal) {
			closeLifeModal();
		}
	});
	document.addEventListener("keydown", (event) => {
		if (event.key === "Escape" && !elements.lifeModal.hidden) {
			closeLifeModal();
		}
	});

	return true;
}
