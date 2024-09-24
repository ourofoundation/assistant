from typing import Dict, List, Tuple

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class ConversationMemory:
    def __init__(
        self,
        short_term_size: int = 5,
        system_message: str = "You are a helpful assistant.",
    ):
        self.short_term_size = short_term_size
        self.short_term: List[str] = []
        self.long_term_summary: str = ""
        self.important_content: List[str] = []
        self.system_message = system_message
        self.message_count: int = 0
        self.vector_store: Dict[int, Tuple[str, np.ndarray]] = {}
        self.vectorizer = TfidfVectorizer()

    def add_message(self, message: Dict[str, str]):
        self.short_term.append(message)
        self.message_count += 1

        # Add to vector store
        # vector = self.vectorizer.fit_transform([message]).toarray()[0]
        # self.vector_store[self.message_count] = (message, vector)

        if len(self.short_term) > self.short_term_size:
            pass
            # print("updating long term memory")
            # self._update_long_term_memory()

    def _update_long_term_memory(self):
        to_summarize = self.short_term[: -self.short_term_size]
        self.short_term = self.short_term[-self.short_term_size :]

        new_summary = self._summarize(to_summarize)
        important_points = self._extract_important_points(to_summarize)

        self.long_term_summary = self._combine_summaries(
            self.long_term_summary, new_summary
        )
        self.important_content.extend(important_points)

    def _summarize(self, messages: List[str]) -> str:
        # Placeholder for actual summarization logic
        return f"Summary of {len(messages)} messages"

    def _extract_important_points(self, messages: List[str]) -> List[str]:
        # Placeholder for importance extraction logic
        return [f"Important point from message {i+1}" for i in range(len(messages))]

    def _combine_summaries(self, old_summary: str, new_summary: str) -> str:
        # Placeholder for summary combination logic
        return f"{old_summary}\n{new_summary}"

    def retrieve_relevant_messages(self, query: str, k: int = 3) -> List[str]:

        return []
        query_vector = self.vectorizer.transform([query]).toarray()[0]

        # Compute similarities
        similarities = {
            msg_id: np.dot(query_vector, msg_vector)
            for msg_id, (_, msg_vector) in self.vector_store.items()
        }

        # Get top k similar messages
        top_k = sorted(similarities.items(), key=lambda x: x[1], reverse=True)[:k]
        return [self.vector_store[msg_id][0] for msg_id, _ in top_k]

    def get_context(self, query: str) -> Tuple[List[str], str, List[str], List[str]]:
        relevant_messages = self.retrieve_relevant_messages(query)
        return (
            self.short_term,
            self.long_term_summary,
            self.important_content,
            relevant_messages,
        )

    def build_context(self, query: str) -> List[Dict[str, str]]:
        relevant_messages = self.retrieve_relevant_messages(query)

        context = []

        if self.system_message:
            context.append({"role": "system", "content": self.system_message})

        if self.long_term_summary:
            context.append(
                {
                    "role": "system",
                    "content": f"Long-term summary: {self.long_term_summary}",
                }
            )

        for point in self.important_content:
            context.append({"role": "system", "content": f"Important point: {point}"})

        for message in relevant_messages:
            context.append(
                {"role": "system", "content": f"Relevant past message: {message}"}
            )

        context.extend(self.short_term)

        context.append({"role": "user", "content": query})

        return context
