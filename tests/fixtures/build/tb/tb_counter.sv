// Original self-checking SV testbench, never executed by build_run.
module tb_counter;
    logic clk = 1'b0;
    logic rst_n = 1'b0;
    logic [7:0] count;

    counter #(.WIDTH(8)) dut (
        .clk(clk), .rst_n(rst_n), .count(count)
    );

    always #5 clk = ~clk;
    initial begin
        #12;
        rst_n = 1'b1;
        repeat (3) @(posedge clk);
        #1;
        if (count !== 8'd3) $fatal(1, "counter mismatch: %0d", count);
        $display("TB_PASS:counter");
        $finish;
    end
endmodule
