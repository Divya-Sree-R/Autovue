function EvaluationPage() {
  return (
    <div className="research-page">

      <header className="route-header research-header">

        <span className="route-eyebrow">
          Research Validation
        </span>

        <h2>
          Evaluation
        </h2>

        <p>
          Experimental results from detector benchmarking,
          OCR validation, road-domain testing and the frozen
          AutoVue multi-frame evaluation.
        </p>

      </header>


      <section className="evaluation-highlight-grid">

        <article className="evaluation-highlight">
          <span>Selected Detector</span>
          <strong>YOLO11n</strong>
          <small>
            Best balance among the tested models
          </small>
        </article>

        <article className="evaluation-highlight">
          <span>Detector mAP50</span>
          <strong>96.66%</strong>
          <small>
            Leakage-safe held-out plate test split
          </small>
        </article>

        <article className="evaluation-highlight">
          <span>Static OCR Exact Match</span>
          <strong>64.29%</strong>
          <small>
            9 / 14 readable held-out plate crops
          </small>
        </article>

        <article className="evaluation-highlight">
          <span>Final Road Clusters</span>
          <strong>43</strong>
          <small>
            Conservative temporal clusters
          </small>
        </article>

      </section>


      <section className="research-grid">

        <article className="panel research-card">

          <div className="panel-heading">
            <div>
              <h3>
                Plate Detector Benchmark
              </h3>
              <p>
                Same leakage-safe held-out test split
              </p>
            </div>
          </div>


          <div className="benchmark-table-wrap">

            <table className="benchmark-table">

              <thead>
                <tr>
                  <th>Model</th>
                  <th>Precision</th>
                  <th>Recall</th>
                  <th>F1</th>
                  <th>mAP50</th>
                  <th>mAP50–95</th>
                  <th>Inference</th>
                </tr>
              </thead>

              <tbody>

                <tr>
                  <td>
                    YOLOv8n
                  </td>
                  <td>94.24%</td>
                  <td>95.90%</td>
                  <td>95.06%</td>
                  <td>96.25%</td>
                  <td>67.07%</td>
                  <td>2.99 ms</td>
                </tr>

                <tr className="benchmark-selected">
                  <td>
                    <strong>
                      YOLO11n
                    </strong>
                    <span className="benchmark-choice">
                      Selected
                    </span>
                  </td>
                  <td>95.44%</td>
                  <td>96.21%</td>
                  <td>95.82%</td>
                  <td>96.66%</td>
                  <td>69.98%</td>
                  <td>3.67 ms</td>
                </tr>

                <tr>
                  <td>
                    YOLO11s
                  </td>
                  <td>95.27%</td>
                  <td>96.25%</td>
                  <td>95.76%</td>
                  <td>96.37%</td>
                  <td>70.63%</td>
                  <td>7.38 ms</td>
                </tr>

              </tbody>

            </table>

          </div>


          <div className="research-note">
            YOLO11n is the selected AutoVue detector because
            it offered the preferred accuracy–latency–model-size
            trade-off among the tested models. This does not
            claim that YOLO11n is universally the best detector.
          </div>

        </article>


        <article className="panel research-card">

          <div className="panel-heading">
            <div>
              <h3>
                Static OCR Evaluation
              </h3>
              <p>
                Held-out manually verified plate crops
              </p>
            </div>
          </div>


          <div className="research-stat-grid">

            <div>
              <span>Readable test crops</span>
              <strong>14</strong>
            </div>

            <div>
              <span>Exact matches</span>
              <strong>9 / 14</strong>
            </div>

            <div>
              <span>Exact-match rate</span>
              <strong>64.29%</strong>
            </div>

            <div>
              <span>Character error rate</span>
              <strong>31.43%</strong>
            </div>

            <div>
              <span>Blank predictions</span>
              <strong>0</strong>
            </div>

            <div>
              <span>Rotation rescues</span>
              <strong>3</strong>
            </div>

          </div>


          <div className="research-warning">
            <strong>
              Important interpretation
            </strong>

            <p>
              64.29% is OCR exact-match accuracy on 14 readable
              held-out ground-truth plate crops. It is not
              end-to-end road-video ANPR accuracy.
            </p>
          </div>

        </article>


        <article className="panel research-card">

          <div className="panel-heading">
            <div>
              <h3>
                Road-Domain Detector Check
              </h3>
              <p>
                Unseen road-video domain shift
              </p>
            </div>
          </div>


          <div className="research-stat-grid compact">

            <div>
              <span>Visible plates</span>
              <strong>57</strong>
            </div>

            <div>
              <span>True positives</span>
              <strong>19</strong>
            </div>

            <div>
              <span>False positives</span>
              <strong>8</strong>
            </div>

            <div>
              <span>False negatives</span>
              <strong>38</strong>
            </div>

            <div>
              <span>Precision</span>
              <strong>70.37%</strong>
            </div>

            <div>
              <span>Recall</span>
              <strong>33.33%</strong>
            </div>

            <div>
              <span>F1</span>
              <strong>45.24%</strong>
            </div>

          </div>


          <div className="research-note">
            The major road-domain weakness was recall.
            The later adaptation experiment was not retained,
            so the frozen detector remains the benchmarked
            leakage-safe model.
          </div>

        </article>


        <article className="panel research-card">

          <div className="panel-heading">
            <div>
              <h3>
                Frozen Multi-Frame Road Evaluation
              </h3>
              <p>
                M25 product reference sequence
              </p>
            </div>
          </div>


          <div className="evaluation-flow">

            <div>
              <strong>45</strong>
              <span>Raw tracker IDs</span>
            </div>

            <span>→</span>

            <div>
              <strong>92</strong>
              <span>Selected crops</span>
            </div>

            <span>→</span>

            <div>
              <strong>43</strong>
              <span>Clusters</span>
            </div>

            <span>→</span>

            <div>
              <strong>8</strong>
              <span>Complete candidates</span>
            </div>

            <span>→</span>

            <div>
              <strong>6</strong>
              <span>Unique strings</span>
            </div>

          </div>


          <div className="status-evaluation-grid">

            <div className="evaluation-status verified">
              <strong>2</strong>
              <span>Verified Full</span>
            </div>

            <div className="evaluation-status corroborated">
              <strong>2</strong>
              <span>Corroborated Fragment</span>
            </div>

            <div className="evaluation-status review">
              <strong>4</strong>
              <span>Needs Review</span>
            </div>

            <div className="evaluation-status rejected">
              <strong>35</strong>
              <span>Rejected</span>
            </div>

          </div>


          <div className="research-warning">
            <strong>
              Evidence status ≠ correctness
            </strong>

            <p>
              VERIFIED_FULL and the other labels express
              temporal evidence strength. They are not
              ground-truth accuracy labels.
            </p>
          </div>

        </article>

      </section>


      <section className="panel protocol-panel">

        <div className="panel-heading">
          <div>
            <h3>
              Evaluation Protocol
            </h3>
            <p>
              Measures taken to avoid overstating results
            </p>
          </div>
        </div>


        <div className="protocol-grid">

          <article>
            <span>01</span>
            <div>
              <strong>
                Leakage-safe detector split
              </strong>
              <p>
                Source identities were separated before
                training, validation and testing to remove
                duplicate-source leakage.
              </p>
            </div>
          </article>

          <article>
            <span>02</span>
            <div>
              <strong>
                Frozen road evaluation
              </strong>
              <p>
                M25 uses the selected models and fixed
                recognition rules rather than tuning the
                system against the final road sequence.
              </p>
            </div>
          </article>

          <article>
            <span>03</span>
            <div>
              <strong>
                Conservative evidence states
              </strong>
              <p>
                Weak single-frame predictions are separated
                from repeatedly supported or fragment-
                corroborated candidates.
              </p>
            </div>
          </article>

          <article>
            <span>04</span>
            <div>
              <strong>
                End-to-end accuracy pending
              </strong>
              <p>
                Human road-video ground truth is still required
                before reporting final end-to-end ANPR accuracy.
              </p>
            </div>
          </article>

        </div>

      </section>


      <footer className="research-footer">
        AutoVue research prototype · Reported metrics retain
        their original evaluation scope.
      </footer>

    </div>
  );
}


export default EvaluationPage;
