function addNameInput() {
  const container = document.getElementById('namesContainer');
  if (container.children.length >= 20) return;

  const index = container.children.length;
  const group = document.createElement('div');
  group.className = 'name-input-group';
  group.innerHTML = `
                    <input type="text" class="form-control" name="names[]" placeholder="Enter name ${index + 1}" required>
                    <button type="button" class="remove-btn" onclick="removeNameInput(this)">Remove</button>
                `;
  container.appendChild(group);
}

function removeNameInput(button) {
  const container = document.getElementById('namesContainer');
  if (container.children.length > 3) {
    button.parentElement.remove();
  }
}

// Add initial name inputs on page load
window.onload = function () {
  for (let i = 0; i < 3; i++) {
    addNameInput();
  }
};