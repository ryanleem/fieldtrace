"""Supabase identity only. No passwords, service keys, or caller-selected user IDs."""
from functools import lru_cache
from uuid import UUID
from urllib.parse import urlsplit

import jwt
from fastapi import Depends, HTTPException, Request, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import get_settings
from app.db.session import get_engine

bearer = HTTPBearer(auto_error=False)


@lru_cache(maxsize=4)
def signing_keys(url):
    return jwt.PyJWKClient(url + '/auth/v1/.well-known/jwks.json',
                          cache_jwk_set=True, lifespan=300, timeout=5)


def verify_token(token: str, settings) -> UUID:
    url = settings.supabase_url.rstrip('/')
    parsed = urlsplit(url)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.query or parsed.fragment or parsed.path:
        raise HTTPException(503, 'Authentication is not configured')
    try:
        if len(token) > 8192:
            raise ValueError('Token too long')
        # Pin issuer, audience and algorithms. Never follow a token-supplied key URL.
        key = signing_keys(url).get_signing_key_from_jwt(token)
        claims = jwt.decode(token, key.key, algorithms=['ES256', 'RS256'],
                            issuer=url + '/auth/v1', audience=settings.supabase_jwt_audience,
                            options={'require': ['exp', 'iat', 'sub', 'iss', 'aud']})
        if claims.get('role') != 'authenticated' or claims.get('is_anonymous', False):
            raise ValueError('Not an authenticated user')
        return UUID(claims['sub'])
    except jwt.PyJWKClientConnectionError:
        raise HTTPException(503, 'Authentication service unavailable') from None
    except (jwt.PyJWTError, ValueError, TypeError, KeyError):
        raise HTTPException(401, 'Invalid or expired sign-in', headers={'WWW-Authenticate': 'Bearer'}) from None


def require_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UUID:
    if credentials is None or credentials.scheme.lower() != 'bearer':
        raise HTTPException(401, 'Sign in to continue', headers={'WWW-Authenticate': 'Bearer'})
    return verify_token(credentials.credentials, get_settings())


def session_access(request: Request, response: Response, user_id: UUID = Depends(require_user)):
    """Router-level gate runs before endpoint/provider dependencies, on every child route.

    Ownership is immutable through the API, so the SQL check remains valid for the
    lifetime of the operation. Service/CLI code is trusted, not a public auth bypass.
    """
    from app.services.user_sessions import owned_session
    response.headers['Cache-Control'] = 'private, no-store'
    if 'session_id' in request.path_params:
        try:
            session_id = UUID(str(request.path_params['session_id']))
        except ValueError:
            raise HTTPException(404, 'Session not found') from None
        owned_session(get_engine(), session_id, user_id)
