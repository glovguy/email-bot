from datetime import datetime
import json
from google.oauth2.credentials import Credentials
from src.models import db, db_session
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship


class OAuthCredential(db.Model):
    __tablename__ = "oauth_credentials"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="oauth_credential")
    token = Column(Text, nullable=False)
    refresh_token = Column(String(512), nullable=True)
    token_uri = Column(String(512), nullable=False)
    client_id = Column(String(512), nullable=False)
    client_secret = Column(String(512), nullable=False)
    scopes = Column(Text, nullable=True)
    expiry = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f'<OAuthCredential user_id: {self.user_id} expiry: {self.expiry}>'

    @property
    def is_expired(self):
        if self.expiry:
            return datetime.utcnow() > self.expiry
        return True

    @classmethod
    def create_or_update(cls, user_id, credentials):
        credential = cls.query.filter_by(user_id=user_id).first()
        if credential:
            credential.token = credentials.token
            credential.refresh_token = credentials.refresh_token
            credential.token_uri = credentials.token_uri
            credential.client_id = credentials.client_id
            credential.client_secret = credentials.client_secret
            credential.scopes = json.dumps(credentials.scopes)
            credential.expiry = credentials.expiry
        else:
            credential = cls(
                user_id=user_id,
                token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri,
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=json.dumps(credentials.scopes),
                expiry=credentials.expiry
            )
            db_session.add(credential)

        db_session.commit()
        return credential

    def to_credentials(self):
        return Credentials(
            token=self.token,
            refresh_token=self.refresh_token,
            token_uri=self.token_uri,
            client_id=self.client_id,
            client_secret=self.client_secret,
            scopes=json.loads(self.scopes) if self.scopes else None
        )
