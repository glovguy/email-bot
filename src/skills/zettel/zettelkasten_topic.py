from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship, Mapped
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
import numpy as np
from typing import List, Tuple
from src.models import db, Vector, cosine_similarity, db_session
from .zettel import Zettel
from .zettel_topic_association import ZettelTopicAssociation
import anthropic
from decouple import config


class ZettelkastenTopic(db.Model):
    __tablename__ = 'zettelkasten_topics'

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(String(1000))
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    user = relationship("User", back_populates="topics")
    centroid_instructor_base_embedding = Column(Vector(768))
    zettels: Mapped[List[Zettel]] = relationship(secondary="zettel_topic_association", back_populates="topics")

    def __repr__(self):
        return f"<ZettelkastenTopic(id={self.id}, name='{self.name}')>"

    def zettels_by_similarity(self):
        return db_session.query(Zettel)\
            .join(ZettelTopicAssociation)\
            .filter(ZettelTopicAssociation.topic_id == self.id)\
            .order_by(ZettelTopicAssociation.similarity_score.desc())\
            .all()

    def similarity_score_for_zettel(self, zettel_id: int):
        association = ZettelTopicAssociation.query.filter_by(zettel_id=zettel_id, topic_id=self.id).first()
        return association.similarity_score if association else None

    @classmethod
    def perform_clustering(cls, embeddings: List[List[float]], num_clusters: int) -> Tuple[np.ndarray, np.ndarray, float]:
        embeddings_array = [np.array(emb) for emb in embeddings]
        kmeans = KMeans(n_clusters=num_clusters, random_state=42)
        cluster_labels = kmeans.fit_predict(embeddings_array)
        centroids = kmeans.cluster_centers_
        score = silhouette_score(embeddings_array, cluster_labels)
        return cluster_labels, centroids, score

    @classmethod
    def experiment_clustering(cls, embeddings: np.ndarray, min_clusters: int, max_clusters: int) -> List[Tuple[int, float]]:
        results = []
        for n_clusters in range(min_clusters, max_clusters + 1):
            _, _, score = cls.perform_clustering(embeddings, n_clusters)
            results.append((n_clusters, score))
        return results

    @classmethod
    def summarize_zettels(cls, zettels):
        zettel_strings = ["[["+ztl.title+"]]"+"\n\n"+ztl.content for ztl in zettels]
        client = anthropic.Anthropic(
            api_key=config('ANTHROPIC_API_KEY')
        )
        summary_messages = [
            {"role": "user", "content": "The following are notes from my Zettelkasten. They are representative notes for a certain topic.\n\n"+"\n\n---\n\n".join(zettel_strings)+"\n\nPlease give a description of this topic. Summarize it briefly."},
        ]
        summary = client.messages.create(
            messages=summary_messages,
            model="claude-3-5-sonnet-20240620",
            max_tokens=100,
            system="The user will provide notes that fit in a Zettelkasten topic group. They are written in markdown. Please summarize this topic briefly. Only include the summarization in your response. Do not use markdown."
        ).content[0].text
        name_messages = [
            {"role": "user", "content": "The following are notes from my Zettelkasten. They are representative notes for a certain topic.\n\n" + "\n\n---\n\n".join(zettel_strings)},
            {"role": "assistant", "content": "Summary: " + summary},
            {"role": "user", "content": "Please make a name for this topic."},
        ]
        name = client.messages.create(
            messages=name_messages,
            model="claude-3-5-sonnet-20240620",
            max_tokens=70,
            system="The following are notes that fit in a Zettelkasten topic group. They are written in markdown. Please generate a title for the topic. Only include the title text in your response. Do not use markdown."
        ).content[0].text
        print("\n\n".join([summary, name]))
        return [summary, name]

    @classmethod
    def create_topics(cls, zettels: List[Zettel], num_clusters: int):
        embeddings = [ztl.instructor_base_embedding for ztl in zettels]
        cluster_labels, centroids, _score = cls.perform_clustering(embeddings, num_clusters)
        topics = []
        for i in range(num_clusters):
            search_results = Zettel.vector_search(centroids[i].tolist(), limit=7)
            top_zettels = [res[0] for res in search_results]
            summary, name = cls.summarize_zettels(top_zettels)
            topic = ZettelkastenTopic(name=name, description=summary, user_id=1, centroid_instructor_base_embedding=centroids[i].tolist())
            db_session.add(topic)
            db_session.commit()
            print("\n\ntopic: ", topic)
            for j in range(len(zettels)):
                if cluster_labels[j] != i:
                    continue
                score = cosine_similarity(zettels[j].instructor_base_embedding, centroids[i])
                association = ZettelTopicAssociation(similarity_score=score, zettel_id=zettels[j].id, topic_id=topic.id)
                db_session.add(association)
            topics.append(topic)
            db_session.add(topic)
        print("topics: ", topics)
        print(topics)
        return topics

    @classmethod
    def create_topics_from_experiment(cls, user_id: int, min_clusters: int, max_clusters: int):
        zettels = db_session.query(Zettel).filter_by(user_id=1).all()
        embeddings = [ztl.instructor_base_embedding for ztl in zettels]
        topic_experiments = ZettelkastenTopic.experiment_clustering(embeddings, min_clusters, max_clusters)
        best_experiment = max(topic_experiments, key=lambda x: x[1])
        num_clusters = best_experiment[0]
        return cls.create_topics(zettels, num_clusters)
