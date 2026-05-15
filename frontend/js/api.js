const API_BASE = "";

function getToken() {
    return localStorage.getItem("token");
}

async function request(method, endpoint, body = null) {
    const headers = {};
    const token = getToken();
    if (token) {
        headers["Authorization"] = "Bearer " + token;
    }

    const options = { method, headers };

    if (body !== null) {
        if (body instanceof FormData) {
            options.body = body;
        } else if (body instanceof URLSearchParams) {
            headers["Content-Type"] = "application/x-www-form-urlencoded";
            options.body = body;
        } else {
            headers["Content-Type"] = "application/json";
            options.body = JSON.stringify(body);
        }
    }

    const response = await fetch(API_BASE + endpoint, options);

    if (response.status === 401) {
        localStorage.removeItem("token");
        window.location.href = "/ui/login.html";
        return;
    }

    if (!response.ok) {
        const error = await response.json().catch(() => ({ detail: response.statusText }));
        throw new Error(error.detail || "Error en la solicitud");
    }

    return response.json();
}
