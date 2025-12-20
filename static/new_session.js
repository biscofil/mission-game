function addNameInput() {
  const container = document.getElementById('namesContainer');
  const index = container.children.length;
  const group = document.createElement('div');
  group.className = 'name-input-group';
  group.innerHTML = `
                    <input type="text" name="names[]" placeholder="Enter name ${index + 1}" required>
                    <button type="button" class="remove-btn" onclick="removeNameInput(this)">Remove</button>
                `;
  container.appendChild(group);
}

function removeNameInput(button) {
  button.parentElement.remove();
}

// Add initial name input on page load
window.onload = function () {
  addNameInput();
};