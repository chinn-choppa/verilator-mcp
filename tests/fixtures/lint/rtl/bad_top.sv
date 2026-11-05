// Intentionally broken synthetic SystemVerilog; Apache-2.0.
module bad_top (
    input  logic a,
    output logic b
);
    assign b = a + ;
endmodule
