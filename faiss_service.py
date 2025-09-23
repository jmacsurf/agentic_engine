from flask import Flask, request, jsonify
import faiss, numpy as np

app = Flask(__name__)
dim = 384
index = faiss.IndexFlatL2(dim)
agent_names = []

@app.route("/index", methods=["POST"])
def index_vectors():
    global agent_names
    data = request.json
    vectors = np.array(data["vectors"]).astype("float32")
    names = data["names"]
    index.add(vectors)
    agent_names.extend(names)
    return jsonify({"status": "ok", "count": len(agent_names)})

@app.route("/search", methods=["POST"])
def search():
    data = request.json
    query = np.array([data["query"]]).astype("float32")
    k = data.get("k", 1)
    D, I = index.search(query, k)
    results = [{"name": agent_names[i], "distance": float(d)} for i, d in zip(I[0], D[0])]
    return jsonify(results)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=6000)
