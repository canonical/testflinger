document.addEventListener('DOMContentLoaded', function() {
    var tagInputs = document.querySelectorAll('.tag-input');

    tagInputs.forEach(function(tagInput) {
        var fieldName = tagInput.getAttribute('data-field-name');
        var textInput = tagInput.querySelector('.tag-input__field');
        var addButton = tagInput.querySelector('.tag-input__add');
        var chipsContainer = tagInput.querySelector('.tag-input__chips');

        addButton.addEventListener('click', function() {
            addTag(chipsContainer, fieldName, textInput);
        });

        textInput.addEventListener('keydown', function(event) {
            if (event.key === 'Enter') {
                // Prevent the form from submitting when adding a tag.
                event.preventDefault();
                addTag(chipsContainer, fieldName, textInput);
            }
        });

        chipsContainer.addEventListener('click', function(event) {
            if (event.target.matches('.p-chip__dismiss')) {
                removeTag(event.target.closest('.p-chip'));
            } else if (event.target.matches('.tag-input__clear-all')) {
                clearAllTags(chipsContainer);
            }
        });
    });
});

/**
 * Creates the "Clear all" button shown alongside the chips whenever at
 * least one tag is selected.
 * @returns {HTMLButtonElement}
 */
function createClearAllButton() {
    var button = document.createElement('button');
    button.type = 'button';
    button.className = 'tag-input__clear-all';
    button.textContent = '\u2715 Clear all';
    return button;
}

/**
 * Adds a new tag (chip) with the value currently in the text input, unless
 * the value is empty or already selected.
 * @param {HTMLElement} chipsContainer
 * @param {String} fieldName
 * @param {HTMLInputElement} textInput
 */
function addTag(chipsContainer, fieldName, textInput) {
    var value = textInput.value.trim();
    if (!value) {
        return;
    }

    var existingValues = Array.from(
        chipsContainer.querySelectorAll('input[type="hidden"]')
    ).map(function(input) {
        return input.value;
    });
    if (existingValues.includes(value)) {
        textInput.value = '';
        return;
    }

    if (!chipsContainer.querySelector('.tag-input__clear-all')) {
        chipsContainer.appendChild(createClearAllButton());
    }

    var chip = document.createElement('span');
    chip.className = 'p-chip';
    chip.innerHTML =
        '<span class="p-chip__value"></span>' +
        '<button type="button" class="p-chip__dismiss">Dismiss</button>';
    chip.querySelector('.p-chip__value').textContent = value;

    var hiddenInput = document.createElement('input');
    hiddenInput.type = 'hidden';
    hiddenInput.name = fieldName;
    hiddenInput.value = value;

    chipsContainer.appendChild(chip);
    chipsContainer.appendChild(hiddenInput);
    textInput.value = '';
}

/**
 * Removes a chip and its associated hidden input from the DOM. If it was
 * the last remaining chip, the "Clear all" button is removed too.
 * @param {HTMLElement} chip
 */
function removeTag(chip) {
    var chipsContainer = chip.parentElement;
    var hiddenInput = chip.nextElementSibling;
    if (hiddenInput && hiddenInput.matches('input[type="hidden"]')) {
        hiddenInput.remove();
    }
    chip.remove();

    if (chipsContainer && !chipsContainer.querySelector('.p-chip')) {
        var clearAllButton = chipsContainer.querySelector('.tag-input__clear-all');
        if (clearAllButton) {
            clearAllButton.remove();
        }
    }
}

/**
 * Removes all chips and hidden inputs from a tag input's chips container.
 * @param {HTMLElement} chipsContainer
 */
function clearAllTags(chipsContainer) {
    chipsContainer.innerHTML = '';
}
