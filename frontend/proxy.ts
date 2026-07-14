import { NextRequest, NextResponse } from "next/server";

const PUBLIC_PATHS = ["/login", "/setup", "/landing", "/images"];
const PUBLIC_EXTENSIONS = [".webp", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".woff", ".woff2", ".ttf", ".css", ".js"];
const AUTH_COOKIE_NAME = "slayz_authenticated";

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;

  const isPublicPath =
    PUBLIC_PATHS.some((path) => pathname === path || pathname.startsWith(`${path}/`)) ||
    PUBLIC_EXTENSIONS.some((ext) => pathname.endsWith(ext));
  const isAuthenticated = request.cookies.get(AUTH_COOKIE_NAME)?.value === "1";

  if (!isAuthenticated && !isPublicPath) {
    const loginUrl = new URL("/login", request.url);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthenticated && pathname === "/login") {
    const dashboardUrl = new URL("/", request.url);
    return NextResponse.redirect(dashboardUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api).*)"],
};
