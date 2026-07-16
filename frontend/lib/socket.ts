"use client";
import { io, Socket } from "socket.io-client";
import { API_BASE_URL, WS_BASE_URL } from "./api";
let socket: Socket | null = null;
let currentToken: string | null = null;

function connect(token: string): Socket {
  const baseUrl = WS_BASE_URL || API_BASE_URL || window.location.origin;
  const httpBaseUrl = baseUrl.replace(/^ws/, "http");
  currentToken = token;
  socket = io(httpBaseUrl, {
    path: "/socket.io", auth: { token }, transports: ["websocket", "polling"],
    withCredentials: true, reconnection: true, reconnectionAttempts: Infinity,
    reconnectionDelay: 750, reconnectionDelayMax: 5000, randomizationFactor: 0.4, timeout: 20000,
  });
  return socket;
}

export function getSocket(token: string): Socket {
  if (socket && currentToken === token) { if (!socket.connected) socket.connect(); return socket; }
  socket?.disconnect();
  return connect(token);
}

if (typeof window !== "undefined") {
  window.addEventListener("slayz-token-updated", ((event: CustomEvent<{ accessToken?: string }>) => {
    const token = event.detail?.accessToken;
    if (token && token !== currentToken) { socket?.disconnect(); connect(token); }
  }) as EventListener);
}

export function disconnectSocket(): void { socket?.disconnect(); socket = null; currentToken = null; }
