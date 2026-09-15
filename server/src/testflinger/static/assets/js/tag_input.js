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
            }
        });
    });
});

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
 * Removes a chip and its associated hidden input from the DOM.
 * @param {HTMLElement} chip
 */
function removeTag(chip) {
    var hiddenInput = chip.nextElementSibling;
    if (hiddenInput && hiddenInput.matches('input[type="hidden"]')) {
        hiddenInput.remove();
    }
    chip.remove();
}
