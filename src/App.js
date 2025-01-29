import React, { useState } from "react";

function App() {
  const [pdf, setPdf] = useState(null); // Armazena o arquivo PDF
  const [csv, setCsv] = useState(null); // Armazena o arquivo CSV
  const [showResults, setShowResults] = useState(false); // Controla a exibição dos resultados
  const [backendResponse, setBackendResponse] = useState(null);

  const handlePdfChange = (e) => {
    const file = e.target.files[0];
    setPdf(file);
  };

  const handleCsvChange = (e) => {
    const file = e.target.files[0];
    setCsv(file);
  };

  const handleSubmit = async () => {
    setShowResults(true); // Exibe os resultados após clicar no botão Enviar

    // Cria o FormData para enviar os arquivos
    const formData = new FormData();
    formData.append("pdf", pdf);
    formData.append("csv", csv);

    try {
      // Envia os arquivos ao backend
      const response = await fetch("http://localhost:5000/upload", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error("Falha ao enviar os arquivos.");
      }

      const result = await response.json();
      console.log(result); // Exibe a resposta do backend

      // Atualiza o estado com a resposta do backend
      setBackendResponse(result.backendResponse); // Aqui você armazena a resposta do backend

      // Exibe as informações retornadas pelo backend
      //alert(`Arquivos recebidos com sucesso! \n Nome do PDF: ${result.pdf_name} \n Nome do CSV: ${result.csv_name}`);
    } catch (error) {
      console.error("Erro ao enviar os arquivos:", error);
    }
  };

  return (
    <div style={{ 
      padding: "20px", 
      backgroundColor: "#00263c", 
      color: "#f2f2f2", 
      minHeight: "100vh", // Garante que cobre toda a tela
      display: "flex", 
      flexDirection: "column", 
      justifyContent: "center", 
      alignItems: "center", 
      boxSizing: "border-box" 
    }}>
      <div style={{
        backgroundColor: "#004d6e",
        padding: "30px",
        borderRadius: "10px",
        boxShadow: "0px 4px 10px rgba(0, 0, 0, 0.5)",
        textAlign: "center",
        width: "100%",
        maxWidth: "500px"
      }}>
        <h1 style={{ color: "#f2f2f2", marginBottom: "20px" }}>AutoMap</h1>
        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "10px" }}>Envie um arquivo PDF:</label>
          <input 
            type="file" 
            accept=".pdf" 
            onChange={handlePdfChange} 
            style={{
              marginBottom: "20px",
              padding: "10px",
              borderRadius: "5px",
              border: "1px solid #f2f2f2",
              width: "100%",
              maxWidth: "300px",
              backgroundColor: "#003a57",
              color: "#f2f2f2"
            }}
          />
        </div>
        <div>
          <label style={{ fontWeight: "bold", display: "block", marginBottom: "10px" }}>Envie um arquivo CSV:</label>
          <input 
            type="file" 
            accept=".csv" 
            onChange={handleCsvChange} 
            style={{
              marginBottom: "20px",
              padding: "10px",
              borderRadius: "5px",
              border: "1px solid #f2f2f2",
              width: "100%",
              maxWidth: "300px",
              backgroundColor: "#003a57",
              color: "#f2f2f2"
            }}
          />
        </div>

        {showResults && backendResponse && (
          <h3 style={{ color: "#f2f2f2", marginTop: "20px" }}>Resultados:</h3>
        )}

        {showResults && backendResponse && (
          <div
            style={{
              border: "1px solid #f2f2f2",
              padding: "10px",
              marginTop: "10px",
              backgroundColor: "#003a57",
              borderRadius: "5px",
              color: "#f2f2f2",
              whiteSpace: "pre-wrap", // Preserva quebras de linha na resposta
            }}
          >
            <p>{backendResponse}</p>
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={!pdf || !csv} // Desabilita o botão se não houver PDF ou CSV
          style={{
            backgroundColor: !pdf || !csv ? "#023858" : "#011F30",
            color: "#f2f2f2",
            padding: "10px 20px",
            border: "none",
            borderRadius: "5px",
            cursor: !pdf || !csv ? "not-allowed" : "pointer",
            fontWeight: "bold",
            outline: "none",
            marginTop: "20px",
            width: "100%",
            maxWidth: "300px"
          }}
          onFocus={(e) => e.target.style.boxShadow = "none"} // Remove sombra ao focar
          onBlur={(e) => e.target.style.boxShadow = "none"} // Remove sombra ao perder foco
        >
          Enviar Documentos
        </button>
        <p style={{ color: "#f2f2f2", fontWeight: "bold"}}>
          Observação:
        </p>
        <p style={{ color: "#f2f2f2", textAlign: "left" }}>
          A correção pode levar até 1 minuto para ser processada após o envio dos documentos. <br />
          Além disso, o produto está em fase de testes. Caso a resposta não seja retornada dentro do tempo estimado, pedimos desculpas, pois ocorreu alguma falha no processo.
        </p>
      </div>
    </div>
  );
}

export default App;

