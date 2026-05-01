export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

export const buildUrl = (path: string) => {
  return `${API_BASE_URL}${path}`;
};
