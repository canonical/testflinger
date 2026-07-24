/**
 * Copy-to-clipboard buttons.
 *
 * Any element carrying a `data-copy-target` attribute copies the textContent
 * of the element matched by that selector to the clipboard when clicked, and
 * briefly shows confirmation feedback.
 */

/**
  Provide brief "Copied!" feedback on a button before restoring its label
  @param {HTMLElement} button the button that was clicked
*/
function showCopyFeedback(button) {
  const label = button.querySelector('span');
  if (!label) {
    return;
  }
  const original = label.textContent;
  label.textContent = 'Copied!';
  button.disabled = true;
  setTimeout(function() {
    label.textContent = original;
    button.disabled = false;
  }, 2000);
}

/**
  Attach click handlers to all copy-to-clipboard buttons on the page
*/
function initCopyButtons() {
  const buttons = [].slice.call(
    document.querySelectorAll('[data-copy-target]')
  );

  buttons.forEach(function(button) {
    button.addEventListener('click', function() {
      const target = document.querySelector(
        button.getAttribute('data-copy-target')
      );
      if (!target || !navigator.clipboard) {
        return;
      }
      navigator.clipboard.writeText(target.textContent).then(function() {
        showCopyFeedback(button);
      });
    });
  });
}

if (typeof document !== 'undefined') {
  document.addEventListener('DOMContentLoaded', initCopyButtons);
}
