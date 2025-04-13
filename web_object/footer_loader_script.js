// Load the footer content from footer.html
function loadFooter() {
    document.addEventListener('DOMContentLoaded', () => {
        fetch('footer.html')
            .then(response => {
                if (!response.ok) {
                    console.error('Footer not found. Status:', response.status);
                    return ''; // No error thrown, just no footer
                }
                return response.text();
            })
            .then(data => {
                const footerElement = document.getElementById('footer');
                if (footerElement) {
                    footerElement.innerHTML = data;

                    // Find and execute any inline script tags in footer.html
                    const scripts = footerElement.getElementsByTagName('script');
                    for (let i = 0; i < scripts.length; i++) {
                        const script = document.createElement('script');
                        script.text = scripts[i].text;
                        document.body.appendChild(script);
                    }
                } else {
                    console.error('Footer element not found in the DOM.');
                }
            })
            .catch(error => {
                console.error('Error fetching footer:', error);
            });
    });
}

// Call the loadFooter function to load footer.html into the page
loadFooter();
