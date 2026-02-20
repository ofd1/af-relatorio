import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_PATHS = ["/"];

export function middleware(request: NextRequest) {
    const { pathname } = request.nextUrl;

    // Allow public paths
    if (PUBLIC_PATHS.includes(pathname)) {
        return NextResponse.next();
    }

    // Check for session cookie
    const session = request.cookies.get("af_session");
    if (!session?.value) {
        const loginUrl = new URL("/", request.url);
        return NextResponse.redirect(loginUrl);
    }

    return NextResponse.next();
}

export const config = {
    matcher: ["/dashboard/:path*", "/upload/:path*", "/depara/:path*", "/export/:path*"],
};
