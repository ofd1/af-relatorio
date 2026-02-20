import axios from "axios";

const api = axios.create({
    baseURL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    withCredentials: true,
    headers: { "Content-Type": "application/json" },
});

// Redirect to login on 401
api.interceptors.response.use(
    (res) => res,
    (error) => {
        if (
            error.response?.status === 401 &&
            typeof window !== "undefined" &&
            window.location.pathname !== "/"
        ) {
            window.location.href = "/";
        }
        return Promise.reject(error);
    }
);

export default api;
